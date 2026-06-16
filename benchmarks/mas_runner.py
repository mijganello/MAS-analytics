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


def extract_report_text(blocks: list[dict]) -> str:
    """Concatenate meaningful text from all report blocks."""
    parts: list[str] = []

    for block in blocks:
        bt = block.get("block_type", "")

        if bt == "text":
            parts.append(block.get("content", ""))

        elif bt == "kpi_card":
            title = block.get("title", "")
            value = block.get("value", "")
            unit  = block.get("unit", "")
            parts.append(f"{title}: {value} {unit}".strip())

        elif bt == "table":
            parts.append(block.get("caption", ""))
            headers = block.get("headers", [])
            rows    = block.get("rows", [])
            if headers:
                parts.append(" | ".join(str(h) for h in headers))
            for row in rows[:100]:
                parts.append(" | ".join(str(c) for c in row))

        elif bt == "insight":
            parts.append(block.get("text", ""))

        elif bt == "executive_summary":
            parts.append(block.get("content", ""))

        elif bt == "comparison":
            parts.append(block.get("title", ""))
            items = block.get("items", [])
            parts.append(json.dumps(items, ensure_ascii=False))

        elif bt == "forecast":
            parts.append(block.get("title", ""))
            parts.append(block.get("summary", ""))
            for pt in block.get("data_points", [])[:20]:
                parts.append(str(pt))

        elif bt == "risk_matrix":
            parts.append(block.get("title", ""))
            for risk in block.get("risks", []):
                name  = risk.get("name", "")
                descr = risk.get("description", "")
                parts.append(f"{name}: {descr}")

        elif bt == "chart":
            parts.append(block.get("title", ""))
            parts.append(block.get("description", ""))

        else:
            # Generic fallback: grab all non-trivial string values
            for v in block.values():
                if isinstance(v, str) and len(v) > 5:
                    parts.append(v)

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
