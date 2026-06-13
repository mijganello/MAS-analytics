from __future__ import annotations
import json
import asyncio
from datetime import datetime
from typing import Any, AsyncIterator
from app.blackboard.pubsub import broker
from app.schemas.tasks import TaskSpec, LoopGuard, EscalationPolicy, TaskGraph
from app.schemas.blackboard import BlackboardEventType, BlackboardMessage, AgentTaskStatus
from app.schemas.blocks import ReportBlock
from app.core.config import settings
from app.core.logging import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class BlackboardManager:
    """Central shared state store. All agent communication flows through here."""

    def __init__(self):
        self._store: dict[str, Any] = {}   # in-memory fallback
        self._redis: Any = None

    async def connect(self, redis_url: str) -> None:
        if REDIS_AVAILABLE:
            try:
                self._redis = await aioredis.from_url(redis_url, decode_responses=True)
                await self._redis.ping()
                logger.info("blackboard_redis_connected")
            except Exception as e:
                logger.warning("blackboard_redis_failed_fallback", error=str(e))
                self._redis = None

    # ── Generic KV ───────────────────────────────────────────────────────────

    async def _set(self, key: str, value: Any, ttl: int = 86400) -> None:
        serialized = json.dumps(value, default=str)
        if self._redis:
            await self._redis.setex(key, ttl, serialized)
        else:
            self._store[key] = value

    async def _get(self, key: str) -> Any | None:
        if self._redis:
            val = await self._redis.get(key)
            return json.loads(val) if val else None
        return self._store.get(key)

    async def _delete(self, key: str) -> None:
        if self._redis:
            await self._redis.delete(key)
        else:
            self._store.pop(key, None)

    # ── Session State ─────────────────────────────────────────────────────────

    async def init_session(self, session_id: str, query: str, file_ids: list[str]) -> None:
        await self._set(f"session:{session_id}", {
            "session_id": session_id,
            "query": query,
            "file_ids": file_ids,
            "status": "running",
            "created_at": datetime.utcnow().isoformat(),
        })

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return await self._get(f"session:{session_id}")

    # ── Tasks ─────────────────────────────────────────────────────────────────

    async def write_task(self, task: TaskSpec) -> None:
        await self._set(
            f"task:{task.task_id}",
            task.model_dump(mode="json"),
            ttl=settings.task_timeout_seconds * 10,
        )
        await self._set(
            f"task_status:{task.task_id}",
            {"task_id": task.task_id, "status": "pending", "retries": 0, "tokens_used": 0},
        )
        await broker.publish(
            f"session:{task.session_id}",
            {"type": BlackboardEventType.TASK_ASSIGNED, "task_id": task.task_id, "department": task.department}
        )

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        return await self._get(f"task:{task_id}")

    async def update_task_status(self, task_id: str, session_id: str, status: str, **kwargs) -> None:
        current = await self._get(f"task_status:{task_id}") or {}
        current.update({"task_id": task_id, "status": status, **kwargs})
        await self._set(f"task_status:{task_id}", current)
        await broker.publish(
            f"session:{session_id}",
            {"type": BlackboardEventType.TASK_STATUS, "task_id": task_id, "status": status, **kwargs},
        )

    # ── Drafts & Verdicts ─────────────────────────────────────────────────────

    async def write_draft(self, task_id: str, draft: dict[str, Any]) -> None:
        await self._set(f"draft:{task_id}", draft)

    async def get_draft(self, task_id: str) -> dict[str, Any] | None:
        return await self._get(f"draft:{task_id}")

    async def write_verdict(self, task_id: str, session_id: str, verdict: dict[str, Any]) -> None:
        await self._set(f"verdict:{task_id}", verdict)
        await broker.publish(
            f"session:{session_id}",
            {"type": BlackboardEventType.VERDICT, "task_id": task_id, "status": verdict.get("status")}
        )

    async def get_verdict(self, task_id: str) -> dict[str, Any] | None:
        return await self._get(f"verdict:{task_id}")

    # ── Approved Blocks ───────────────────────────────────────────────────────

    async def write_approved_block(self, session_id: str, block: dict[str, Any]) -> None:
        block_id = block.get("block_id", "")
        await self._set(f"block:{block_id}", block)
        # Append to session block list
        key = f"session_blocks:{session_id}"
        blocks = await self._get(key) or []
        blocks.append(block_id)
        await self._set(key, blocks)
        await broker.publish(
            f"session:{session_id}",
            {"type": BlackboardEventType.BLOCK_APPROVED, "block_id": block_id, "block": block},
        )

    async def get_block(self, block_id: str) -> dict[str, Any] | None:
        return await self._get(f"block:{block_id}")

    async def get_session_blocks(self, session_id: str) -> list[dict[str, Any]]:
        key = f"session_blocks:{session_id}"
        block_ids = await self._get(key) or []
        blocks = []
        for bid in block_ids:
            b = await self.get_block(bid)
            if b:
                blocks.append(b)
        return sorted(blocks, key=lambda x: x.get("order", 0))

    # ── Loop Guard ────────────────────────────────────────────────────────────

    async def increment_retry(self, task_id: str) -> int:
        status = await self._get(f"task_status:{task_id}") or {}
        retries = status.get("retries", 0) + 1
        status["retries"] = retries
        await self._set(f"task_status:{task_id}", status)
        return retries

    # ── Task Graph ────────────────────────────────────────────────────────────

    async def write_task_graph(self, session_id: str, graph: dict[str, Any]) -> None:
        await self._set(f"graph:{session_id}", graph)

    async def get_task_graph(self, session_id: str) -> dict[str, Any] | None:
        return await self._get(f"graph:{session_id}")

    # ── Session Summary (for Orchestrator, token-efficient) ───────────────────

    async def get_session_summary(self, session_id: str) -> dict[str, Any]:
        blocks = await self.get_session_blocks(session_id)
        graph = await self.get_task_graph(session_id)
        completed = [b.get("block_type") for b in blocks]
        return {
            "completed_block_types": completed,
            "block_count": len(blocks),
            "pending_tasks": (graph or {}).get("execution_groups", []),
        }

    # ── SSE Event Stream ──────────────────────────────────────────────────────

    async def subscribe_session(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        async for event in broker.subscribe(f"session:{session_id}"):
            yield event

    async def mark_session_done(self, session_id: str) -> None:
        session = await self._get(f"session:{session_id}") or {}
        session["status"] = "complete"
        await self._set(f"session:{session_id}", session)
        await broker.publish(
            f"session:{session_id}",
            {"type": BlackboardEventType.SESSION_DONE, "session_id": session_id},
        )

    # ── Agent Interaction Log ──────────────────────────────────────────────────

    async def append_log(
        self,
        session_id: str,
        event_type: str,
        agent: str,
        message: str,
        *,
        task_id: str | None = None,
        department: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Append a structured log event for the session."""
        key = f"agentlog:{session_id}"
        events = await self._get(key) or []
        events.append({
            "ts": datetime.utcnow().isoformat(),
            "type": event_type,
            "agent": agent,
            "message": message,
            "task_id": task_id,
            "department": department,
            "details": details or {},
        })
        await self._set(key, events, ttl=86400)
        # Also publish as SSE event for live view
        await broker.publish(
            f"session:{session_id}",
            {
                "type": "agent_log",
                "ts": events[-1]["ts"],
                "event_type": event_type,
                "agent": agent,
                "message": message,
                "task_id": task_id,
                "department": department,
                "details": details or {},
            },
        )

    async def get_log(self, session_id: str) -> list[dict]:
        """Return all log events for a session."""
        return await self._get(f"agentlog:{session_id}") or []

    async def close(self) -> None:
        pass


blackboard = BlackboardManager()
