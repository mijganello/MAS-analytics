"""
Benchmark reporter — deterministic metrics only.

No FAS, RSS, Score, Efficiency, Cost.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.table import Table

RESULTS_DIR = Path(__file__).parent / "results"

CSV_FIELDS = [
    "dataset_id", "mode",
    "latency_s", "token_count",
    "answers_correct", "answers_total",
    "hi", "npi",
    "error",
]

console = Console()


def save_csv(all_metrics: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in all_metrics:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def save_markdown(
    all_metrics: list[dict],
    comparisons: list[dict],
    path: Path,
    timestamp: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"# Benchmark Results — {timestamp}",
        "",
        "> DeepSeek-only. Метрики: **answers** (correct/total), **PUI** (доля чисел не из источника), **NPI**, latency, tokens.",
        "",
        "## Результаты по прогонам",
        "",
        "| Dataset | Mode | Answers | PUI ↓ | NPI ↑ | Latency (s) | Tokens |",
        "|---------|------|---------|------|-------|------------|--------|",
    ]

    for m in all_metrics:
        err = " ⚠" if m.get("error") else ""
        ans = f"{m.get('answers_correct','?')}/{m.get('answers_total','?')}"
        lines.append(
            f"| {m.get('dataset_id','')} "
            f"| {m.get('mode','')}{err} "
            f"| {ans} "
            f"| {m.get('hi','?')} "
            f"| {m.get('npi','?')} "
            f"| {m.get('latency_s','?')} "
            f"| {m.get('token_count','?')} |"
        )

    lines += ["", "---", "", "## Сравнение MAS vs Naive", ""]
    lines += [
        "| Dataset | MAS answers | Naive answers | Total | MAS PUI | Naive PUI | MAS NPI | Naive NPI | Latency× | Tokens× |",
        "|---------|-------------|---------------|-------|--------|----------|---------|-----------|----------|---------|",
    ]

    for c in comparisons:
        mas_a = f"{c.get('mas_answers_correct','?')}/{c.get('answers_total','?')}"
        nav_a = f"{c.get('naive_answers_correct','?')}/{c.get('answers_total','?')}"
        lines.append(
            f"| {c.get('dataset_id','')} "
            f"| {mas_a} "
            f"| {nav_a} "
            f"| {c.get('answers_total','?')} "
            f"| {c.get('mas_hi','?')} "
            f"| {c.get('naive_hi','?')} "
            f"| {c.get('mas_npi','?')} "
            f"| {c.get('naive_npi','?')} "
            f"| {c.get('latency_ratio','?')}× "
            f"| {c.get('token_ratio','?')}× |"
        )

    # Per-dataset answer breakdown
    lines += ["", "---", "", "## Детализация ответов по вопросам", ""]
    by_dataset: dict[str, list[dict]] = {}
    for m in all_metrics:
        by_dataset.setdefault(m["dataset_id"], []).append(m)

    for ds_id, runs in sorted(by_dataset.items()):
        lines.append(f"### {ds_id}")
        lines.append("")
        for m in runs:
            mode = m.get("mode", "?")
            lines.append(f"**{mode.upper()}** — {m.get('answers_correct',0)}/{m.get('answers_total',0)}")
            for chk in m.get("answer_checks", []):
                mark = "✓" if chk.get("matched") else "✗"
                lines.append(
                    f"- {mark} `{chk.get('key')}`: ожид. **{chk.get('expected')}** "
                    f"(±{chk.get('tolerance')*100:.1f}%) — {chk.get('question','')}"
                )
            if m.get("hi_samples"):
                lines.append(f"- PUI samples (галлюцинации): `{m['hi_samples']}`")
            # Include the actual response text (truncated for readability)
            resp = m.get("response_text", "")
            if resp:
                lines.append("")
                lines.append("<details>")
                lines.append(f"<summary>📄 Полный ответ {mode.upper()}</summary>")
                lines.append("")
                lines.append("```")
                # Truncate to 3000 chars to keep markdown readable
                lines.append(resp[:3000] + ("…" if len(resp) > 3000 else ""))
                lines.append("```")
                lines.append("")
                lines.append("</details>")
            lines.append("")

    lines += [
        "---",
        "",
        "## Методология",
        "",
        "- **Answers**: для каждого вопроса из `expected_numbers` проверяется наличие числа "
        "в ответе в пределах `tolerance`.",
        "- **PUI**: доля чисел в ответе (≥2), не совпадающих ни с одним ожидаемым ответом (±2%).",
        "- **NPI**: доля «точных» (некруглых) чисел ≥100 — информационная метрика.",
        "- **Latency / Tokens**: wall-clock и счётчик токенов.",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def print_dataset_metrics_table(all_metrics: list[dict]) -> None:
    table = Table(title="[bold]Результаты[/bold]", box=box.SIMPLE_HEAD)
    table.add_column("Dataset", style="cyan", no_wrap=True)
    table.add_column("Mode", style="bold")
    table.add_column("Answers", justify="right", style="bold")
    table.add_column("PUI ↓", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Tokens", justify="right")

    for m in all_metrics:
        err = " ⚠" if m.get("error") else ""
        mode_str = ("MAS" if m.get("mode") == "mas" else "Naive") + err
        mode_col = "green" if m.get("mode") == "mas" else "yellow"
        ans = f"{m.get('answers_correct','?')}/{m.get('answers_total','?')}"
        ans_col = "green" if m.get("answers_correct") == m.get("answers_total") else "yellow"
        table.add_row(
            m.get("dataset_id", ""),
            f"[{mode_col}]{mode_str}[/{mode_col}]",
            f"[{ans_col}]{ans}[/{ans_col}]",
            str(m.get("hi", "?")),
            str(m.get("npi", "?")),
            f"{m.get('latency_s','?')}s",
            str(m.get("token_count", "?")),
        )
    console.print(table)


def print_summary_table(comparisons: list[dict]) -> None:
    table = Table(
        title="[bold]MAS vs Naive[/bold]",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Dataset", style="cyan", no_wrap=True)
    table.add_column("MAS\nanswers", justify="right", style="green")
    table.add_column("Naive\nanswers", justify="right", style="yellow")
    table.add_column("MAS PUI", justify="right")
    table.add_column("Naive PUI", justify="right")
    table.add_column("Latency×", justify="right")
    table.add_column("Tokens×", justify="right")

    for c in comparisons:
        total = c.get("answers_total", "?")
        table.add_row(
            c.get("dataset_id", ""),
            f"{c.get('mas_answers_correct','?')}/{total}",
            f"{c.get('naive_answers_correct','?')}/{total}",
            str(c.get("mas_hi", "?")),
            str(c.get("naive_hi", "?")),
            f"{c.get('latency_ratio','?')}×",
            f"{c.get('token_ratio','?')}×",
        )
    console.print(table)


def make_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
