from __future__ import annotations
import asyncio
import json
from typing import Any, AsyncIterator
from app.core.logging import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class PubSubBroker:
    """Async pub/sub broker. Redis in production, in-memory for tests."""

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url
        self._redis: Any = None
        self._queues: dict[str, list[asyncio.Queue]] = {}

    async def connect(self, redis_url: str | None = None) -> None:
        if redis_url:
            self._redis_url = redis_url
        if self._redis_url and REDIS_AVAILABLE:
            try:
                # socket_timeout=None keeps pub/sub connection alive indefinitely
                self._redis = await aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_timeout=None,
                    socket_keepalive=True,
                )
                await self._redis.ping()
                logger.info("pubsub_redis_connected")
            except Exception as e:
                logger.info("pubsub_inmemory_fallback", error=str(e))
                self._redis = None
        else:
            logger.info("pubsub_inmemory_mode")

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        payload = json.dumps(message)
        if self._redis:
            try:
                await self._redis.publish(channel, payload)
            except Exception as e:
                logger.warning("pubsub_publish_error", error=str(e))
                # Fallback to in-memory
                for q in self._queues.get(channel, []):
                    await q.put(message)
        else:
            for q in self._queues.get(channel, []):
                await q.put(message)

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        if self._redis:
            async for msg in self._redis_subscribe(channel):
                yield msg
        else:
            async for msg in self._memory_subscribe(channel):
                yield msg

    async def _redis_subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Redis pub/sub with reconnect on timeout."""
        while True:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(channel)
                async for raw in pubsub.listen():
                    if raw["type"] == "message":
                        try:
                            yield json.loads(raw["data"])
                        except json.JSONDecodeError:
                            pass
                    elif raw["type"] == "subscribe":
                        continue  # subscription confirmation, skip
                return  # clean exit
            except Exception as e:
                logger.warning("pubsub_redis_listen_error", error=str(e))
                await asyncio.sleep(0.5)
                return  # exit generator on error, SSE handler will reconnect

    async def _memory_subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(channel, []).append(q)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield msg
                except asyncio.TimeoutError:
                    # yield sentinel so SSE can send keep-alive
                    yield {"type": "__keepalive__"}
        finally:
            try:
                self._queues[channel].remove(q)
            except ValueError:
                pass

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()


broker = PubSubBroker()
