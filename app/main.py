from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import shutdown_pools, startup_pools
from .routers import analyst as analyst_router
from .routers import auth as auth_router
from .routers import history as history_router
from .routers import schema as schema_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("retail-analyst")
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_pools()
    log.info("Connection pools opened (db=%s host=%s)", _settings.PG_DB, _settings.PG_HOST)
    try:
        yield
    finally:
        shutdown_pools()
        log.info("Connection pools closed")


app = FastAPI(
    title="MCP Retail SQL Analyst",
    description="LLM-powered safe analytics over a Kimball retail data warehouse.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mcp-retail-sql-analyst", "version": "1.0.0"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth_router.router)
app.include_router(schema_router.router)
app.include_router(analyst_router.router)
app.include_router(history_router.router)
