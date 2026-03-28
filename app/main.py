"""
Autonomous Support Architect — FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.db.pgvector import ensure_schema, close_pool
from app.config import settings
from app.observability import configure_logging


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Autonomous Support Architect — env=%s", settings.APP_ENV)
    await ensure_schema()
    logger.info("Database schema verified")
    yield
    await close_pool()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Autonomous Support Architect",
    version="0.1.0",
    description="Security-first LangGraph middleware for enterprise support automation",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
