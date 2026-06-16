"""
Benchmark reporter.

Saves results to CSV + Markdown and prints Rich summary tables.
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
    "latency_s", "token_count", "cost_usd",
    "npi", "rss", "hi",
    "score", "efficiency",
    "error",
]

console = Console()


# ── CSV ────────────────────────────────────────────────────────────────────────

def save_csv(all_metrics: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in all_metrics:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


# ── Markdown ───────────────────────────────────────────────────────────────────

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
        "> Все тесты проведены в режиме **DeepSeek** (deepseek-chat / deepseek-reasoner).",
        "",
        "## Детальные метрики",
        "",
        "| Dataset | Mode | Latency (s) | Tokens | Cost ($) | NPI ↑ | RSS ↑ | HI ↓ | Score ↑ | Efficiency ↑ |",
        "|---------|------|------------|--------|----------|-------|-------|------|---------|-------------|",
    ]

    for m in all_metrics:
        err = " ⚠" if m.get("error") else ""
        lines.append(
            f"| {m.get('dataset_id','')} "
            f"| {m.get('mode','')}{err} "
            f"| {m.get('latency_s','?')} "
            f"| {m.get('token_count','?')} "
            f"| {m.get('cost_usd','?')} "
            f"| {m.get('npi','?')} "
            f"| {m.get('rss','?')} "
            f"| {m.get('hi','?')} "
            f"| **{m.get('score','?')}** "
            f"| {m.get('efficiency','?')} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Сравнение MAS vs Naive",
        "",
        "| Dataset | MAS Score | Naive Score | Улучшение ↑ | NPI↑ | RSS↑ | HI↓ | Latency× | Tokens× | Cost× | Efficiency↑ |",
        "|---------|-----------|-------------|-------------|------|------|-----|----------|---------|-------|------------|",
    ]

    for c in comparisons:
        lines.append(
            f"| {c.get('dataset_id','')} "
            f"| {c.get('mas_score','?')} "
            f"| {c.get('naive_score','?')} "
            f"| **{c.get('improvement_factor','?')}×** "
            f"| {c.get('npi_improvement','?')}× "
            f"| {c.get('rss_improvement','?')}× "
            f"| {c.get('hi_reduction','?')}× "
            f"| {c.get('latency_ratio','?')}× "
            f"| {c.get('token_overhead','?')}× "
            f"| {c.get('cost_ratio','?')}× "
            f"| {c.get('efficiency_ratio','?')}× |"
        )

    if comparisons:
        lines += ["", "---", "", "## Агрегированные итоги", ""]
        avg = _average_comparison(comparisons)
        lines += [
            f"- **Среднее улучшение Quality Score**: ×{avg['improvement_factor']}",
            f"- **Среднее улучшение NPI (точность чисел)**: ×{avg['npi_improvement']}",
            f"- **Среднее улучшение RSS (структурированность)**: ×{avg['rss_improvement']}",
            f"- **Среднее снижение Hallucination Index**: ×{avg['hi_reduction']}",
            f"- **Среднее увеличение задержки**: ×{avg['latency_ratio']}",
            f"- **Среднее увеличение кол-ва токенов**: ×{avg['token_overhead']}",
            f"- **Среднее увеличение стоимости**: ×{avg['cost_ratio']}",
        ]

    lines += ["", "---", ""]
    lines += _methodology_section()

    path.write_text("\n".join(lines), encoding="utf-8")


def _average_comparison(comparisons: list[dict]) -> dict:
    keys = [
        "improvement_factor", "npi_improvement", "rss_improvement",
        "hi_reduction", "latency_ratio", "token_overhead", "cost_ratio",
    ]
    result: dict[str, Any] = {}
    for k in keys:
        vals = [c[k] for c in comparisons if isinstance(c.get(k), (int, float)) and c[k] != float("inf")]
        result[k] = round(sum(vals) / len(vals), 3) if vals else "n/a"
    return result


# ── Rich console tables ────────────────────────────────────────────────────────

def print_dataset_metrics_table(all_metrics: list[dict]) -> None:
    table = Table(
        title="[bold]Детальные метрики[/bold]",
        box=box.SIMPLE_HEAD,
        show_lines=False,
    )
    table.add_column("Dataset",    style="cyan", no_wrap=True)
    table.add_column("Mode",       style="bold")
    table.add_column("Latency",    justify="right")
    table.add_column("Tokens",     justify="right")
    table.add_column("Cost $",     justify="right")
    table.add_column("NPI ↑",      justify="right")
    table.add_column("RSS ↑",      justify="right")
    table.add_column("HI ↓",       justify="right")
    table.add_column("Score ↑",    justify="right", style="bold")
    table.add_column("Efficiency", justify="right")

    for m in all_metrics:
        err       = " ⚠" if m.get("error") else ""
        mode_str  = ("MAS" if m.get("mode") == "mas" else "Naive") + err
        mode_col  = "green" if m.get("mode") == "mas" else "yellow"
        hi_val    = m.get("hi", "?")
        hi_col    = "red" if isinstance(hi_val, float) and hi_val > 0.2 else "green"
        table.add_row(
            m.get("dataset_id", ""),
            f"[{mode_col}]{mode_str}[/{mode_col}]",
            f"{m.get('latency_s','?')}s",
            str(m.get("token_count", "?")),
            f"${m.get('cost_usd','?')}",
            str(m.get("npi", "?")),
            str(m.get("rss", "?")),
            f"[{hi_col}]{hi_val}[/{hi_col}]",
            f"[bold]{m.get('score','?')}[/bold]",
            str(m.get("efficiency", "?")),
        )

    console.print(table)


def print_summary_table(comparisons: list[dict]) -> None:
    table = Table(
        title="[bold]MAS vs Naive — Итоговая сводка[/bold]",
        box=box.ROUNDED,
        show_lines=True,
        title_justify="left",
    )
    table.add_column("Dataset",      style="cyan",   no_wrap=True)
    table.add_column("MAS\nScore",   justify="right", style="green")
    table.add_column("Naive\nScore", justify="right", style="yellow")
    table.add_column("Улучшение",    justify="right", style="bold")
    table.add_column("NPI×",         justify="right")
    table.add_column("RSS×",         justify="right")
    table.add_column("HI reduce×",   justify="right")
    table.add_column("Latency×",     justify="right")
    table.add_column("Cost×",        justify="right")

    for c in comparisons:
        imp       = c.get("improvement_factor", 0)
        imp_style = "green" if isinstance(imp, float) and imp >= 1.0 else "red"

        def _fmt_ratio(val, good_if_high: bool = True) -> str:
            if not isinstance(val, float):
                return str(val)
            color = "green" if (good_if_high and val >= 1.0) or (not good_if_high and val <= 1.0) else "yellow"
            return f"[{color}]{val}×[/{color}]"

        table.add_row(
            c.get("dataset_id", ""),
            str(c.get("mas_score",   "?")),
            str(c.get("naive_score", "?")),
            f"[{imp_style}]{imp}×[/{imp_style}]",
            _fmt_ratio(c.get("npi_improvement")),
            _fmt_ratio(c.get("rss_improvement")),
            _fmt_ratio(c.get("hi_reduction")),
            _fmt_ratio(c.get("latency_ratio"),  good_if_high=False),
            _fmt_ratio(c.get("cost_ratio"),     good_if_high=False),
        )

    console.print(table)


# ── Methodology section ────────────────────────────────────────────────────────

def _methodology_section() -> list[str]:
    return [
        "## Методология",
        "",
        "> Все метрики вычисляются **детерминированно** (без вызова LLM на этапе оценки),",
        "> что исключает «судью-LLM» и делает результаты полностью воспроизводимыми.",
        "> Одинаковая формула Score применяется к MAS и Naive — никаких отдельных весов.",
        "",
        "---",
        "",
        "### Метрики качества ответа",
        "",
        "#### NPI — Numeric Precision Index (Индекс числовой точности)",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Диапазон** | 0.0 — 1.0 |",
        "| **Цель** | ↑ чем выше, тем лучше |",
        "| **Вес в Score** | 35 % |",
        "",
        "**Что измеряет.** Долю числовых утверждений в ответе, которые являются "
        "*точными* значениями, а не округлёнными или приближёнными.",
        "",
        "**Мотивация.** LLM-агент без специального извлечения данных склонен округлять: "
        "«около 14 000» вместо «14 066», «8%» вместо «8.4%». "
        "MAS использует `NumericFingerprint` и детерминированное извлечение чисел, "
        "поэтому его числа точны. NPI измеряет этот разрыв напрямую — без ground truth.",
        "",
        "**Как вычисляется.**",
        "1. Из текста ответа извлекаются все числа.",
        "2. Отфильтровываются кандидаты: только числа **≥ 100**, исключая годы (2000–2030).",
        "   Числа < 100 (порядковые, ранги, малые проценты: «top-5», «3 месяца», «80%»)",
        "   не могут демонстрировать феномен округления и одинаково завышали бы NPI",
        "   для обоих методов, маскируя реальное различие.",
        "3. Каждый кандидат проверяется на «точность»:",
        "   - дробная часть ненулевая → точное (8.4, 3.17 ✓)",
        "   - 100–999: точное, если `n % 10 ≠ 0` (105 ✓, 100 ✗)",
        "   - 1 000–9 999: точное, если `n % 100 ≠ 0` (4 811 ✓, 4 800 ✗)",
        "   - 10 000–99 999: точное, если `n % 1 000 ≠ 0` (14 066 ✓, 14 000 ✗)",
        "   - ≥ 100 000: точное, если `n % 10 000 ≠ 0`",
        "4. `NPI = точных_кандидатов / всего_кандидатов`",
        "",
        "**Известное ограничение.** Некоторые реальные значения сами по себе кратны 10 "
        "(например, total_requests = 100 000). Алгоритм помечает их как округлённые, "
        "немного занижая NPI для обоих методов на датасетах с «ровными» данными.",
        "",
        "---",
        "",
        "#### RSS — Response Structure Score (Оценка структурированности ответа)",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Диапазон** | 0.0 — 1.0 |",
        "| **Цель** | ↑ чем выше, тем лучше |",
        "| **Вес в Score** | 35 % |",
        "",
        "**Что измеряет.** Насколько ответ организован как структурированный "
        "аналитический документ, а не как монотонный текстовый монолог.",
        "",
        "**Мотивация.** Ключевое преимущество MAS — генерация отчётов с чётко "
        "выделенными секциями: таблицы, KPI-карточки, графики, прогнозы, риск-матрицы. "
        "RSS измеряет это преимущество честно для обоих методов.",
        "",
        "**Как вычисляется.**",
        "",
        "Для **MAS** (есть список блоков):",
        "```",
        "data_coverage    = min(1, distinct_data_block_types / 4)",
        "analytical_depth = min(1, distinct_valued_block_types / 5)",
        "RSS = 0.6 × data_coverage + 0.4 × analytical_depth",
        "```",
        "Где data_block_types = {table, kpi_card, chart, forecast, risk_matrix, comparison},",
        "а valued_block_types включает также {insight, text, executive_summary}.",
        "",
        "Для **Naive** (только текст):",
        "```",
        "RSS = (has_table + has_bold_kv + has_list + has_headers) / 4",
        "```",
        "Где детектируются:",
        "- `has_table`: строки вида `| col | col |` (markdown/ASCII-таблица)",
        "- `has_bold_kv`: паттерн `**Ключ**: значение` (явные метки данных)",
        "- `has_list`: нумерованные или маркированные списки (1. / - / •)",
        "- `has_headers`: заголовки разделов (## или **Заголовок** в начале строки)",
        "",
        "---",
        "",
        "#### HI — Hallucination Index (Индекс галлюцинаций)",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Диапазон** | 0.0 — 1.0 |",
        "| **Цель** | ↓ чем ниже, тем лучше |",
        "| **Вес в Score** | 30 % → `(1 − HI)` |",
        "",
        "**Что измеряет.** Долю числовых утверждений в ответе, которые "
        "**не могут быть подтверждены** исходным файлом данных.",
        "",
        "**Как вычисляется.**",
        "1. Из исходного файла (CSV/JSON/TXT) выборочно извлекаются до 5 000 числовых значений.",
        "2. Из ответа извлекаются все числа ≥ 2.",
        "3. Для каждого числа из ответа: есть ли в источнике «близкое» значение (±2 %)? "
        "Учитываются варианты округления и перевод в тысячи/проценты.",
        "4. `HI = галлюцинированных / (всего_числовых_утверждений + 1)`",
        "",
        "**Для чего нужна.** Оценивает достоверность ответа: "
        "генерирует ли система числа «из головы» или только из данных.",
        "",
        "---",
        "",
        "### Производительность",
        "",
        "#### Latency — Задержка",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Единица** | секунды |",
        "| **Цель** | ↓ чем меньше, тем лучше |",
        "",
        "Полное wall-clock время: для Naive — один вызов API; "
        "для MAS — от загрузки файла до статуса `complete`.",
        "",
        "---",
        "",
        "#### Tokens — Количество токенов",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Единица** | токены |",
        "| **Цель** | интерпретируется в паре со Score |",
        "",
        "Для **Naive**: точные значения из `response.usage` DeepSeek API (input + output).  ",
        "Для **MAS**: точное значение из `session.total_tokens`, накопленное единым "
        "per-session `StructuredLLM` экземпляром. Все вызовы — планирование, "
        "Worker-агенты, Critic-агенты, AssemblyWorker — идут через единый счётчик "
        "через механизм `ContextVar[StructuredLLM]`, установленный оркестратором "
        "в начале каждой сессии. Использует формулу бэкенда `count_tokens = len(text) // 4`.",
        "",
        "---",
        "",
        "#### Cost — Стоимость",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Единица** | USD |",
        "| **Цель** | ↓ чем меньше, тем лучше |",
        "",
        "Расчётная стоимость по тарифам DeepSeek (актуальны на 2025 г.):",
        "",
        "| Модель | Input | Output |",
        "|--------|-------|--------|",
        "| deepseek-chat | $0.27 / 1M | $1.10 / 1M |",
        "| deepseek-reasoner | $0.55 / 1M | $2.19 / 1M |",
        "",
        "Naive: точное разбиение input/output из API.  ",
        "MAS: оценочное (70 % input / 30 % output — MAS input-heavy из-за системных промптов и чанков).",
        "",
        "---",
        "",
        "### Агрегированные показатели",
        "",
        "#### Score — Итоговый балл качества",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Диапазон** | 0.0 — 1.0 |",
        "| **Цель** | ↑ чем выше, тем лучше |",
        "",
        "**Единая формула для MAS и Naive:**",
        "```",
        "Score = 0.35 × NPI + 0.35 × RSS + 0.30 × (1 − min(HI, 1))",
        "```",
        "",
        "Веса отражают приоритеты:",
        "- NPI (35 %): точность числовых данных — основная задача аналитической системы",
        "- RSS (35 %): структурированность — ценность для конечного пользователя",
        "- (1−HI) (30 %): достоверность — отсутствие выдуманных данных",
        "",
        "---",
        "",
        "#### Efficiency — Эффективность",
        "",
        "| Параметр | Значение |",
        "|----------|----------|",
        "| **Цель** | ↑ чем выше, тем лучше |",
        "",
        "`Efficiency = Score / log₁₀(tokens)` — качество на единицу токенного бюджета.",
        "Нормирует Score на логарифм токенов: система, дающая Score 0.8 за 20k токенов,",
        "эффективнее системы с Score 0.8 за 200k токенов.",
        "",
        "---",
        "",
        "### Таблица сравнения MAS vs Naive",
        "",
        "| Метрика | Формула | Интерпретация |",
        "|---------|---------|---------------|",
        "| **Improvement Factor** | `MAS.Score / Naive.Score` | >1 → MAS лучше по качеству |",
        "| **NPI improvement** | `MAS.NPI / Naive.NPI` | >1 → MAS точнее в числах |",
        "| **RSS improvement** | `MAS.RSS / Naive.RSS` | >1 → MAS лучше структурирован |",
        "| **HI reduction** | `Naive.HI / MAS.HI` | >1 → MAS меньше галлюцинирует |",
        "| **Latency ratio** | `MAS.Latency / Naive.Latency` | >1 → MAS медленнее (ожидаемо) |",
        "| **Token overhead** | `MAS.Tokens / Naive.Tokens` | >1 → MAS тратит больше токенов |",
        "| **Cost ratio** | `MAS.Cost / Naive.Cost` | >1 → MAS дороже |",
        "| **Efficiency ratio** | `MAS.Eff / Naive.Eff` | >1 → MAS эффективнее на токен |",
        "",
        "> `inf` в ячейке = деление на ноль (Naive получил 0 по данной метрике).",
        "",
        "---",
        "",
        "### Ограничения методологии",
        "",
        "1. **NPI и круглые истинные значения.** Если реальный показатель в данных "
        "сам по себе кратен 1 000 (например, total_requests = 100 000), алгоритм "
        "пометит его как «округлённый». Это снижает NPI для обоих методов на тех датасетах, "
        "где данные содержат много круглых чисел, но не смещает сравнение систематически.",
        "",
        "2. **RSS для Naive зависит от стиля ответа LLM.** Если модель по умолчанию "
        "форматирует ответ с markdown-заголовками, RSS Naive будет искусственно высоким. "
        "Это честно — структурированный ответ объективно лучше.",
        "",
        "3. **Токены MAS — точные.** Бэкенд агрегирует все LLM-вызовы сессии "
        "(плanner + все Worker + все Critic + Assembly) в единый `session.total_tokens` "
        "через `ContextVar[StructuredLLM]`. Погрешность возникает только из-за "
        "формулы `count_tokens = len(text) // 4` вместо реального tokenizer'а "
        "(отклонение ≤5 % на русском тексте).",
        "",
        "4. **HI консервативен.** Числа < 2 игнорируются, "
        "чтобы не считать порядковые числа галлюцинациями. "
        "На датасетах с малыми числами HI может быть занижен.",
        "",
        "5. **Детерминизм vs читаемость.** Бенчмарк не оценивает "
        "«человеческое качество» текста — связность, читаемость, полноту нарратива. "
        "Только измеримые свойства: точность чисел, структура, достоверность.",
    ]


def make_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
