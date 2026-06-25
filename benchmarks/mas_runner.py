"""
MAS (Multi-Agent System) runner.

Uploads the fixture file to the running backend, creates a session with
llm_provider=deepseek, polls until completion, and returns the full report.

Token counting note
-------------------
Since the backend refactor (set_session_llm / ContextVar approach), every
LLM call — planning, worker, critic, assembly — goes through the same
per-session StructuredLLM instance.  session.total_tokens now contains the
exact total accumulated across the entire pipeline.

The /api/reports/{id}/log endpoint also returns the session_complete event
whose details.total_tokens field mirrors the DB value, so we have two
consistent sources.  We prefer the DB value (session metadata) as it's
the authoritative store and requires no log parsing.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

POLL_INTERVAL  = 5    # seconds between status polls
MAX_POLL_TIME  = 900  # 15 minutes hard limit
HTTP_TIMEOUT   = httpx.Timeout(60.0, read=120.0)


def _mime_type(path: Path) -> str:
    return {
        ".csv":  "text/csv",
        ".json": "application/json",
        ".txt":  "text/plain",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(path.suffix.lower(), "application/octet-stream")


def _row_to_str(row: object) -> str:
    """Serialize a table row to a pipe-delimited string of its *values*.

    Blocks store rows as dicts {col_key: value}.  The old code iterated
    ``for c in row`` which yields dict keys (strings), losing all numeric
    values and making NPI always 0 for table-heavy reports.
    """
    if isinstance(row, dict):
        return " | ".join(str(v) for v in row.values())
    # list/tuple row — original behaviour
    return " | ".join(str(c) for c in row)


def _kpi_value_str(value: object) -> str:
    """Normalise a KPI card value so that _extract_numbers can find it.

    The worker model stores ``value`` as a string (e.g. "15 200 000",
    "15,200,000", "3.17", "₽14 066", "85%").  We strip non-numeric
    decoration and keep the raw number so downstream regex can pick it up.

    We intentionally return the *raw number string*, not a reformatted
    float, so that _is_precise() sees the original precision.
    """
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).strip()
    # Strip currency/percent/unit prefix/suffix characters
    s = s.replace("₽", "").replace("$", "").replace("€", "").replace("%", "")
    s = s.replace("руб", "").replace("тыс", "").replace("млн", "").replace("млрд", "")
    # Collapse comma-as-thousands: "15,200,000" → "15200000"
    # Rule: if pattern is X,YYY,ZZZ (multiple comma-separated 3-digit groups) → thousands
    import re as _re
    s = _re.sub(r'(\d),(\d{3})(?=,\d{3}|\b)', r'\1\2', s)  # multi-group
    s = _re.sub(r'(\d),(\d{3})\b', r'\1\2', s)             # single group
    # K/M/B/тыс/млн suffixes → raw integer string
    # Must run after comma-strip so "15,2К" works too
    suffix_map = [
        (_re.compile(r'^([+-]?\d+(?:[.,]\d+)?)\s*[Kк]$'), 1_000),
        (_re.compile(r'^([+-]?\d+(?:[.,]\d+)?)\s*[Мм]$'), 1_000_000),
        (_re.compile(r'^([+-]?\d+(?:[.,]\d+)?)\s*[Bb]$'), 1_000_000_000),
    ]
    for pat, mult in suffix_map:
        m = pat.match(s.strip())
        if m:
            try:
                num = float(m.group(1).replace(',', '.')) * mult
                return str(int(num) if num == int(num) else num)
            except ValueError:
                pass
    return s.strip()


def extract_report_text(blocks: list[dict]) -> str:
    """Concatenate meaningful text from all report blocks.

    Produces a plain-text representation that both HI (hallucination) and
    NPI (numeric precision) metrics can consume.  Key correctness rules:

    - Table rows are stored as dicts {col_key: value}; we emit values, not keys.
    - KPI ``value`` fields are normalised (thousand separators stripped, K/M
      suffixes expanded) so the NPI regex can detect large exact numbers.
    - Forecast / comparison / chart numeric payloads are included.
    """
    parts: list[str] = []

    for block in blocks:
        bt = block.get("block_type", "")

        if bt == "text":
            parts.append(block.get("content", ""))

        elif bt == "kpi_card":
            title  = block.get("title", "") or block.get("metric_name", "")
            value  = block.get("value", "")
            unit   = block.get("unit", "")
            norm   = _kpi_value_str(value)
            # Parenthesise unit so _extract_numbers doesn't re-expand
            # suffixes like "млн"/"млрд" as multipliers (value is already
            # in those units).
            unit_str = f" ({unit})" if unit else ""
            parts.append(f"{title}: {norm}{unit_str}".strip())
            # Also include delta/benchmark if present
            for extra_key in ("delta", "delta_pct", "benchmark"):
                v = block.get(extra_key)
                if v is not None:
                    parts.append(f"{extra_key}: {v}")

        elif bt == "table":
            parts.append(block.get("title", ""))
            parts.append(block.get("caption", ""))
            columns = block.get("columns", [])
            headers = block.get("headers", [])
            # columns is a list of dicts {"key":..., "label":...}; extract labels
            if columns and isinstance(columns[0], dict):
                headers = [c.get("label", c.get("key", "")) for c in columns]
            if headers:
                parts.append(" | ".join(str(h) for h in headers))
            rows = block.get("rows", [])
            for row in rows[:200]:
                parts.append(_row_to_str(row))
            # totals row
            totals = block.get("totals_row")
            if totals:
                parts.append(_row_to_str(totals))

        elif bt == "insight":
            parts.append(block.get("headline", ""))
            parts.append(block.get("explanation", ""))
            parts.append(block.get("text", ""))   # legacy field
            for sd in block.get("supporting_data", []):
                parts.append(str(sd))

        elif bt == "executive_summary":
            parts.append(block.get("overall_conclusion", ""))
            parts.append(block.get("content", ""))
            for finding in block.get("key_findings", []):
                parts.append(str(finding))
            for rec in block.get("recommendations", []):
                parts.append(str(rec))

        elif bt == "comparison":
            parts.append(block.get("title", ""))
            parts.append(block.get("analysis", ""))
            for item in block.get("items", []):
                if isinstance(item, dict):
                    parts.append(item.get("label", ""))
                    metrics = item.get("metrics", {})
                    if isinstance(metrics, dict):
                        for k, v in metrics.items():
                            parts.append(f"{k}: {v}")
                else:
                    parts.append(str(item))

        elif bt == "forecast":
            parts.append(block.get("title", ""))
            parts.append(block.get("summary", ""))
            parts.append(block.get("metric_name", ""))
            for pt in block.get("historical", [])[:20]:
                if isinstance(pt, dict):
                    parts.append(f"{pt.get('period','')}: {pt.get('value','')}")
                else:
                    parts.append(str(pt))
            for pt in block.get("forecast", [])[:10]:
                if isinstance(pt, dict):
                    parts.append(
                        f"{pt.get('period','')}: {pt.get('value','')} "
                        f"[{pt.get('lower_bound','')}-{pt.get('upper_bound','')}]"
                    )
                else:
                    parts.append(str(pt))
            for pt in block.get("data_points", [])[:20]:   # legacy field
                parts.append(str(pt))

        elif bt == "risk_matrix":
            parts.append(block.get("title", ""))
            for risk in block.get("risks", []):
                if isinstance(risk, dict):
                    parts.append(
                        f"{risk.get('name','')}: {risk.get('description','')}"
                    )

        elif bt == "chart":
            parts.append(block.get("title", ""))
            parts.append(block.get("description", ""))
            parts.append(block.get("caption", ""))
            # Try to extract numeric values from vega-lite data payload
            spec = block.get("vega_lite_spec", {})
            if isinstance(spec, dict):
                data = spec.get("data", {})
                if isinstance(data, dict):
                    for item in data.get("values", [])[:50]:
                        if isinstance(item, dict):
                            parts.append(_row_to_str(item))

        else:
            # Generic fallback: grab all non-trivial string/numeric values
            for v in block.values():
                if isinstance(v, str) and len(v) > 5:
                    parts.append(v)
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    parts.append(str(v))

    return "\n".join(p for p in parts if p.strip())


async def run_mas(
    fixture: dict,
    backend_url: str,
) -> dict[str, Any]:
    """
    Run the MAS pipeline for one fixture.

    Args:
        fixture:     dict with data_file, ground_truth
        backend_url: base URL of the running backend, e.g. http://localhost:8000

    Returns:
        raw result dict ready for metrics computation
    """
    gt         = fixture["ground_truth"]
    query      = gt["query"]
    dataset_id = fixture["dataset_id"]
    data_file: Path = fixture["data_file"]

    t0 = time.monotonic()
    error: str | None = None

    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=HTTP_TIMEOUT) as http:

            # ── 1. Upload file ─────────────────────────────────────────────
            with open(data_file, "rb") as fh:
                up_resp = await http.post(
                    "/api/files/upload",
                    files={"files": (data_file.name, fh, _mime_type(data_file))},
                )
            up_resp.raise_for_status()
            file_id: str = up_resp.json()[0]["file_id"]

            # ── 2. Wait for file processing (up to 60 s) ──────────────────
            for _ in range(30):
                st = await http.get(f"/api/files/{file_id}/status")
                st_data = st.json()
                if st_data["status"] == "done":
                    break
                if st_data["status"] == "error":
                    raise RuntimeError(f"File processing error: {st_data}")
                await asyncio.sleep(2)

            # ── 3. Create session (force DeepSeek) ─────────────────────────
            sess_resp = await http.post(
                "/api/sessions",
                json={
                    "query":        query,
                    "file_ids":     [file_id],
                    "llm_provider": "deepseek",
                    "report_title": f"Benchmark: {dataset_id}",
                },
            )
            sess_resp.raise_for_status()
            session_id: str = sess_resp.json()["session_id"]

            # ── 4. Poll until complete ─────────────────────────────────────
            deadline = time.monotonic() + MAX_POLL_TIME
            sess_data: dict = {}
            while time.monotonic() < deadline:
                await asyncio.sleep(POLL_INTERVAL)
                poll = await http.get(f"/api/sessions/{session_id}")
                sess_data = poll.json()
                if sess_data.get("status") in ("complete", "failed"):
                    break

            latency      = time.monotonic() - t0
            total_tokens = sess_data.get("total_tokens") or 0
            status       = sess_data.get("status", "unknown")

            if status == "failed":
                return _error_result(dataset_id, latency, total_tokens, "session failed")

            if status not in ("complete",):
                return _error_result(dataset_id, latency, total_tokens, f"timeout: status={status}")

            # ── 5. Fetch report ────────────────────────────────────────────
            rep_resp = await http.get(f"/api/reports/{session_id}")
            rep_resp.raise_for_status()
            report = rep_resp.json()

            blocks    = report.get("blocks", [])
            resp_text = extract_report_text(blocks)

            # ── 6. Real token count from backend (all workers share one counter) ─
            # total_tokens in the session record is now accurate: it covers
            # planning + all worker + all critic + assembly calls.
            token_count = total_tokens

    except Exception as exc:
        latency = time.monotonic() - t0
        return _error_result(dataset_id, latency, 0, str(exc))

    return {
        "dataset_id":    dataset_id,
        "mode":          "mas",
        "latency":       latency,
        "token_count":   token_count,
        "tokens_in":     int(token_count * 0.70),  # MAS is input-heavy: prompts + context
        "tokens_out":    int(token_count * 0.30),
        "response_text": resp_text,
        "blocks":        blocks,
        "error":         None,
    }



def _error_result(dataset_id: str, latency: float, tokens: int, msg: str) -> dict:
    return {
        "dataset_id":    dataset_id,
        "mode":          "mas",
        "latency":       latency,
        "token_count":   tokens,
        "tokens_in":     0,
        "tokens_out":    0,
        "response_text": "",
        "blocks":        [],
        "error":         msg,
    }
