from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.storage.postgres import get_db
from app.schemas.api import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    postgres_ok = "ok"
    redis_ok = "ok"
    llm_ok = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        postgres_ok = "error"

    try:
        from app.blackboard.pubsub import broker
        if broker._redis:
            await broker._redis.ping()
    except Exception:
        redis_ok = "degraded"

    return HealthResponse(
        status="ok" if postgres_ok == "ok" else "degraded",
        postgres=postgres_ok,
        redis=redis_ok,
        llm_api=llm_ok,
    )
