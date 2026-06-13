from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, logger
from app.storage.postgres import init_db, close_db
from app.blackboard.board import blackboard
from app.blackboard.pubsub import broker

# Import all tools to register them
import app.tools  # noqa


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("startup", environment=settings.environment)

    await init_db()
    await broker.connect(settings.redis_url)
    await blackboard.connect(settings.redis_url)

    yield

    await broker.close()
    await close_db()
    logger.info("shutdown")


app = FastAPI(
    title="MAS Analytics API",
    description="Multi-Agent System for Controlled LLM Analytical Reporting",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://frontend"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import files, sessions, reports, health

app.include_router(files.router)
app.include_router(sessions.router)
app.include_router(reports.router)
app.include_router(health.router)


@app.get("/")
async def root():
    return {"message": "MAS Analytics API", "docs": "/docs", "health": "/api/health"}
