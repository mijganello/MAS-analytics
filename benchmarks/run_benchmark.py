#!/usr/bin/env python3
"""
MAS Analytics Benchmark
=======================

Сравнивает многоагентную систему (MAS) с наивным методом (прямой вызов DeepSeek).
Все тесты проводятся ТОЛЬКО в режиме DeepSeek.

Использование
-------------
    # Все 5 датасетов:
    python benchmarks/run_benchmark.py

    # Только 3 датасета:
    python benchmarks/run_benchmark.py --datasets 01,02,03

    # Кастомный URL бэкенда:
    python benchmarks/run_benchmark.py --backend http://localhost:8000

    # Только наивный метод (если бэкенд не запущен):
    python benchmarks/run_benchmark.py --naive-only

Требования
----------
    pip install -r benchmarks/requirements.txt
    DEEPSEEK_API_KEY=sk-... в .env или переменной окружения
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── ensure benchmarks/ is on sys.path for relative imports ───────────────────
BENCH_DIR = Path(__file__).resolve().parent
ROOT_DIR  = BENCH_DIR.parent
sys.path.insert(0, str(BENCH_DIR))

# ── third-party (installed via benchmarks/requirements.txt) ──────────────────
try:
    import httpx
    from dotenv import load_dotenv
    from openai import AsyncOpenAI
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
    )
except ImportError as exc:
    print(f"Missing dependency: {exc}. Run: pip install -r benchmarks/requirements.txt")
    sys.exit(1)

# ── local modules ─────────────────────────────────────────────────────────────
from metrics.aggregate import compute_all_metrics, compare_results  # noqa: E402
from naive_runner import run_naive                                   # noqa: E402
from mas_runner import run_mas                                       # noqa: E402
from reporter import (                                               # noqa: E402
    make_timestamp, print_dataset_metrics_table,
    print_summary_table, save_csv, save_markdown,
    RESULTS_DIR,
)

# ── load .env (root first, then benchmarks/) ─────────────────────────────────
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BENCH_DIR / ".env")

DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL    = "deepseek-chat"

FIXTURES_DIR = BENCH_DIR / "fixtures"

console = Console()


# ── fixture discovery ─────────────────────────────────────────────────────────

def discover_fixtures(filter_ids: set[str] | None = None, big: bool = False) -> list[dict]:
    """Scan fixtures/ directory and return sorted list of (data_file, ground_truth) pairs."""
    fixtures: list[dict] = []
    pattern = "*_big_ground_truth.json" if big else "*_ground_truth.json"

    for gt_file in sorted(FIXTURES_DIR.glob(pattern)):
        # Skip big fixtures when in small mode and vice versa
        if not big and "_big_ground_truth" in gt_file.name:
            continue
        if big and "_big_ground_truth" not in gt_file.name:
            continue
        try:
            gt = json.loads(gt_file.read_text(encoding="utf-8"))
        except Exception as exc:
            console.print(f"[yellow]⚠ Cannot parse {gt_file.name}: {exc}[/]")
            continue

        data_file = FIXTURES_DIR / gt["file"]
        if not data_file.exists():
            console.print(f"[yellow]⚠ Data file not found: {data_file.name}, skipping.[/]")
            continue

        dataset_id: str = gt["dataset_id"]

        if filter_ids:
            # match by prefix (e.g. "01" matches "01_server_logs")
            if not any(dataset_id.startswith(fid.strip()) for fid in filter_ids):
                continue

        fixtures.append({
            "dataset_id":   dataset_id,
            "data_file":    data_file,
            "gt_file":      gt_file,
            "ground_truth": gt,
        })

    return fixtures


# ── metrics wrapper ────────────────────────────────────────────────────────────

def compute_metrics(raw: dict, fixture: dict) -> dict[str, Any]:
    """Wrap compute_all_metrics; return zeroed result on error."""
    dataset_id = raw["dataset_id"]
    is_mas     = raw["mode"] == "mas"
    gt         = fixture["ground_truth"]

    if raw.get("error"):
        total = len(gt.get("expected_numbers", []))
        return {
            "dataset_id":      dataset_id,
            "mode":            raw["mode"],
            "latency_s":       round(raw["latency"], 2),
            "token_count":     raw.get("token_count", 0),
            "answers_correct": 0,
            "answers_total":   total,
            "hi":              1.0,
            "npi":             0.0,
            "answer_checks":   [],
            "hi_samples":      [],
            "error":           raw["error"],
        }

    m = compute_all_metrics(
        response_text   = raw["response_text"],
        ground_truth    = gt,
        latency_seconds = raw["latency"],
        token_count     = max(raw["token_count"], 1),
        blocks          = raw["blocks"] if is_mas else None,
        source_file     = fixture["data_file"],
        is_mas          = is_mas,
    )
    m["error"] = None
    m["response_text"] = raw.get("response_text", "")
    return m


# ── backend health check ───────────────────────────────────────────────────────

async def check_backend(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.get(f"{url}/api/health")
            r.raise_for_status()
        return True
    except Exception:
        return False


# ── main ───────────────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> None:
    backend_url = args.backend
    naive_only  = args.naive_only
    big         = args.big
    filter_ids  = set(args.datasets.split(",")) if args.datasets else None

    # ── banner ────────────────────────────────────────────────────────────────
    mode_str = "BIG" if big else "small"
    console.print(Panel.fit(
        f"[bold cyan]MAS Analytics Benchmark[/bold cyan]\n"
        f"[dim]DeepSeek-only mode · {mode_str} fixtures[/dim]",
        border_style="cyan",
    ))

    # ── validate DeepSeek key ─────────────────────────────────────────────────
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("sk-your"):
        console.print(
            "[red]✗ DEEPSEEK_API_KEY не задан. "
            "Добавьте его в .env или переменную окружения.[/red]"
        )
        sys.exit(1)

    deepseek_client = AsyncOpenAI(
        api_key  = DEEPSEEK_API_KEY,
        base_url = DEEPSEEK_BASE_URL,
    )

    # ── backend availability ──────────────────────────────────────────────────
    if naive_only:
        backend_available = False
        console.print("[yellow]⚠ --naive-only: MAS-тесты пропускаются.[/yellow]")
    else:
        backend_available = await check_backend(backend_url)
        if backend_available:
            console.print(f"[green]✓ Бэкенд доступен: {backend_url}[/green]")
        else:
            console.print(
                f"[yellow]⚠ Бэкенд недоступен ({backend_url}). "
                "MAS-тесты будут пропущены.[/yellow]"
            )

    # ── discover fixtures ─────────────────────────────────────────────────────
    fixtures = discover_fixtures(filter_ids, big=big)
    if not fixtures:
        hint = " --big" if big else ""
        console.print(
            f"[red]Файлы фикстур не найдены. "
            f"Сначала запустите: python benchmarks/generate_fixtures/generate_all.py{hint}[/red]"
        )
        sys.exit(1)

    console.print(
        f"\n[bold]Датасетов: {len(fixtures)}[/bold]  "
        f"Модель: [cyan]{DEEPSEEK_MODEL}[/cyan]  "
        f"MAS: [{'green' if backend_available else 'red'}]"
        f"{'включён' if backend_available else 'отключён'}[/]"
    )
    console.print()

    # ── run benchmarks ────────────────────────────────────────────────────────
    all_metrics:  list[dict] = []
    comparisons:  list[dict] = []

    total = len(fixtures)
    for idx, fixture in enumerate(fixtures, 1):
        ds = fixture["dataset_id"]
        console.rule(f"[bold cyan]{idx}/{total}: {ds}[/bold cyan]")

        # ── Naive ──────────────────────────────────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            transient=True,
            console=console,
        ) as prog:
            task = prog.add_task("[yellow]Naive (deepseek-chat)…", total=None)
            naive_raw = await run_naive(fixture, deepseek_client, model=DEEPSEEK_MODEL)

        if naive_raw["error"]:
            console.print(
                f"  [yellow]Naive[/yellow] [red]ERROR[/red]: {naive_raw['error']}"
            )
        else:
            console.print(
                f"  [yellow]Naive[/yellow] "
                f"[green]✓[/green] "
                f"{naive_raw['latency']:.1f}s | "
                f"{naive_raw['token_count']} tokens | "
                f"{len(naive_raw['response_text'])} chars"
            )

        naive_m = compute_metrics(naive_raw, fixture)
        all_metrics.append(naive_m)

        # ── MAS ────────────────────────────────────────────────────────────
        if backend_available:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                transient=True,
                console=console,
            ) as prog:
                prog.add_task("[green]MAS (polling…)", total=None)
                mas_raw = await run_mas(fixture, backend_url)

            if mas_raw["error"]:
                console.print(
                    f"  [green]MAS[/green]   [red]ERROR[/red]: {mas_raw['error']}"
                )
            else:
                blocks_n = len(mas_raw["blocks"])
                console.print(
                    f"  [green]MAS[/green]   "
                    f"[green]✓[/green] "
                    f"{mas_raw['latency']:.1f}s | "
                    f"{mas_raw['token_count']} tokens | "
                    f"{blocks_n} blocks"
                )

            mas_m = compute_metrics(mas_raw, fixture)
            all_metrics.append(mas_m)

            # ── Compare ────────────────────────────────────────────────────
            comparison = compare_results(mas_m, naive_m)
            comparisons.append(comparison)

            mas_a = f"{mas_m['answers_correct']}/{mas_m['answers_total']}"
            nav_a = f"{naive_m['answers_correct']}/{naive_m['answers_total']}"
            console.print(
                f"  Answers: MAS=[green]{mas_a}[/green] "
                f"Naive=[yellow]{nav_a}[/yellow] | "
                f"PUI: MAS={mas_m['hi']} Naive={naive_m['hi']}"
            )

        console.print()

    # ── save results ──────────────────────────────────────────────────────────
    ts       = make_timestamp()
    csv_path = RESULTS_DIR / f"benchmark_{ts}.csv"
    md_path  = RESULTS_DIR / f"benchmark_{ts}.md"

    save_csv(all_metrics, csv_path)
    save_markdown(
        all_metrics,
        comparisons,
        md_path,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    console.print(f"[bold green]✓ Результаты сохранены:[/bold green]")
    console.print(f"  CSV:      {csv_path}")
    console.print(f"  Markdown: {md_path}")
    console.print()

    # ── print tables ──────────────────────────────────────────────────────────
    print_dataset_metrics_table(all_metrics)
    console.print()

    if comparisons:
        print_summary_table(comparisons)


# ── CLI entry point ────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MAS Analytics Benchmark (DeepSeek only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--backend",
        default=os.getenv("BACKEND_URL", "http://localhost:8000"),
        metavar="URL",
        help="URL бэкенда (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--datasets",
        default=None,
        metavar="IDS",
        help="Через запятую: номера датасетов для запуска (e.g. 01,02,03). По умолчанию — все.",
    )
    parser.add_argument(
        "--naive-only",
        action="store_true",
        help="Запустить только наивный метод (бэкенд не нужен).",
    )
    parser.add_argument(
        "--big",
        action="store_true",
        help="Использовать большие фикстуры (_big) вместо маленьких (по умолчанию — маленькие).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
