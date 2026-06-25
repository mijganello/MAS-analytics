"""
Deterministic table parsing and aggregate computation for QuantWorker.

In strict mode we build a computation table from parsed CSV/table data so
answers do not depend on LLM block formatting.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd


def _try_float(s: str) -> float | None:
    s = str(s).strip()
    if not s or s.lower() in ("-", "n/a", "null", "none", "—", "н/д", "nan"):
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _is_timestamp(value: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", str(value).strip()))


def _coerce_cell(header: str, cell: str) -> Any:
    cell = str(cell).strip()
    if _is_timestamp(cell):
        return cell
    num = _try_float(cell)
    return num if num is not None else cell


def parse_pipe_table(content: str) -> list[dict[str, Any]]:
    lines = [ln for ln in content.strip().splitlines() if ln.strip()]
    if len(lines) < 2 or " | " not in lines[0]:
        return []
    headers = [h.strip() for h in lines[0].split("|")]
    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split("|")]
        if len(cells) != len(headers):
            continue
        rows.append({h: _coerce_cell(h, c) for h, c in zip(headers, cells)})
    return rows


def parse_table_block(block: dict) -> list[dict[str, Any]]:
    rows = block.get("rows") or []
    if not rows:
        return []
    columns = block.get("columns") or []
    if columns and isinstance(columns[0], dict):
        keys = [c.get("key") or c.get("label", "") for c in columns]
    else:
        keys = list(rows[0].keys()) if isinstance(rows[0], dict) else []
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            parsed.append({k: _coerce_cell(k, row.get(k, "")) for k in keys if k in row})
        elif isinstance(row, list) and keys:
            parsed.append({k: _coerce_cell(k, v) for k, v in zip(keys, row)})
    return parsed


def collect_table_rows(chunks: list[dict], data_context: dict | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for chunk in chunks:
        content = chunk.get("content", "")
        for row in parse_pipe_table(content):
            key = str(row)
            if key not in seen:
                seen.add(key)
                rows.append(row)

    for block in (data_context or {}).values():
        if not isinstance(block, dict) or block.get("block_type") != "table":
            continue
        for row in parse_table_block(block):
            key = str(row)
            if key not in seen:
                seen.add(key)
                rows.append(row)

    return rows


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            cols.append(col)
            continue
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() >= max(2, int(len(df) * 0.6)):
            df[col] = converted
            cols.append(col)
    return cols


def _string_columns(df: pd.DataFrame, numeric: list[str]) -> list[str]:
    return [c for c in df.columns if c not in numeric]


def _append_metric(metrics: list[dict], label: str, value: float | int) -> None:
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return
    if isinstance(value, float):
        if value == int(value):
            value = int(value)
        else:
            value = round(value, 4)
    metrics.append({"metric": label, "value": value})


def compute_metric_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    df = pd.DataFrame(rows)
    if df.empty:
        return []

    numeric = _numeric_columns(df)
    string_cols = _string_columns(df, numeric)
    metrics: list[dict[str, Any]] = []

    _append_metric(metrics, "Количество строк", len(df))

    for col in numeric:
        s = df[col].dropna()
        if s.empty:
            continue
        _append_metric(metrics, f"SUM({col})", float(s.sum()))
        _append_metric(metrics, f"MEAN({col})", float(s.mean()))
        _append_metric(metrics, f"MAX({col})", float(s.max()))
        _append_metric(metrics, f"MIN({col})", float(s.min()))

        for thresh in (3, 4, 4.0, 18):
            cnt = int((s < thresh).sum())
            if cnt:
                _append_metric(metrics, f"COUNT({col} < {thresh})", cnt)
        for thresh in (18,):
            cnt = int((s > thresh).sum())
            if cnt:
                _append_metric(metrics, f"COUNT({col} > {thresh})", cnt)
        for val in (0, 1, 2, 3, 4, 5):
            cnt = int((s == val).sum())
            if cnt:
                _append_metric(metrics, f"COUNT({col} = {val})", cnt)

    err_cols = [c for c in numeric if re.search(r"error|4xx|5xx|ошиб", c, re.I)]
    if len(err_cols) >= 2:
        combined = float(df[err_cols].sum().sum())
        _append_metric(metrics, "SUM(errors combined)", combined)

    req_col = next((c for c in numeric if re.search(r"^requests$|запрос", c, re.I)), None)
    if err_cols and req_col:
        total_err = float(df[err_cols].sum().sum())
        total_req = float(df[req_col].sum())
        if total_req:
            _append_metric(metrics, "Error rate %", total_err / total_req * 100)

    success_col = next((c for c in numeric if re.search(r"success|успех", c, re.I)), None)
    if success_col is not None:
        _append_metric(metrics, "Success rate %", float(df[success_col].sum()) / len(df) * 100)

    rating_col = next((c for c in numeric if re.search(r"rating|grade|оценк|gpa", c, re.I)), None)
    weight_col = next(
        (
            c for c in numeric
            if c != rating_col and re.search(r"count|review|student|отзыв|студент", c, re.I)
        ),
        None,
    )
    if rating_col and weight_col:
        denom = float(df[weight_col].sum())
        if denom:
            wavg = float((df[rating_col] * df[weight_col]).sum()) / denom
            _append_metric(metrics, f"WEIGHTED_AVG({rating_col})", wavg)

    for str_col in string_cols:
        _append_metric(metrics, f"UNIQUE({str_col})", int(df[str_col].nunique()))
        for num_col in numeric:
            grouped_sum = df.groupby(str_col, dropna=False)[num_col].sum()
            if grouped_sum.empty:
                continue
            _append_metric(metrics, f"TOP_SUM({num_col}) by {str_col}", float(grouped_sum.max()))

            grouped_mean = df.groupby(str_col, dropna=False)[num_col].mean()
            _append_metric(metrics, f"TOP_MEAN({num_col}) by {str_col}", float(grouped_mean.max()))

            for key, val in grouped_sum.items():
                _append_metric(metrics, f"SUM({num_col})|{str_col}={key}", float(val))

    return metrics


def build_computation_table_block(rows: list[dict[str, Any]]) -> dict | None:
    metric_rows = compute_metric_rows(rows)
    if not metric_rows:
        return None

    return {
        "block_type": "table",
        "title": "Результаты вычислений",
        "columns": [
            {"key": "metric", "label": "Показатель"},
            {"key": "value", "label": "Значение"},
        ],
        "rows": metric_rows,
    }
