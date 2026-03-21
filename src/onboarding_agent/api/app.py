"""FastAPI application — REST + WebSocket endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from onboarding_agent.api.routes import analyze, health, qa
from onboarding_agent.services.cache import AnalysisCache
from onboarding_agent.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    cache = AnalysisCache()
    await cache.init_db()
    yield


app = FastAPI(
    title="Codebase Onboarding Agent",
    description="Automated codebase analysis and onboarding documentation generator",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router, prefix="/api")
app.include_router(qa.router, prefix="/api")
