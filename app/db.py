"""Connection pools for the warehouse.

Two pools are exposed:
- `app_pool`: full app role (used for auth tables, audit writes, schema introspection).
- `ro_pool`: read-only role used for executing analyst-generated SQL. Falls back
  to the app role if the read-only user does not exist yet, so the system works
  out of the box and tightens automatically once you run `sql/05_app_tables.sql`.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg_pool import ConnectionPool

from .config import get_settings

log = logging.getLogger(__name__)

_settings = get_settings()

app_pool = ConnectionPool(
    conninfo=_settings.app_dsn,
    min_size=1,
    max_size=8,
    kwargs={"autocommit": False, "options": f"-c search_path={_settings.SCHEMA_NAME},public"},
    open=False,
)


def _build_ro_pool() -> ConnectionPool:
    try:
        pool = ConnectionPool(
            conninfo=_settings.ro_dsn,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": True, "options": f"-c search_path={_settings.SCHEMA_NAME},public"},
            open=False,
        )
        pool.open(wait=True, timeout=5)
        return pool
    except Exception as exc:  # noqa: BLE001
        log.warning("RO pool unavailable (%s); falling back to app role for read queries.", exc)
        fallback = ConnectionPool(
            conninfo=_settings.app_dsn,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": True, "options": f"-c search_path={_settings.SCHEMA_NAME},public"},
            open=False,
        )
        fallback.open(wait=True, timeout=5)
        return fallback


ro_pool: ConnectionPool | None = None


def startup_pools() -> None:
    global ro_pool
    app_pool.open(wait=True, timeout=5)
    ro_pool = _build_ro_pool()


def shutdown_pools() -> None:
    try:
        app_pool.close()
    except Exception:
        pass
    if ro_pool is not None:
        try:
            ro_pool.close()
        except Exception:
            pass


@contextmanager
def app_conn() -> Iterator[psycopg.Connection]:
    with app_pool.connection() as conn:
        yield conn


@contextmanager
def ro_conn() -> Iterator[psycopg.Connection]:
    assert ro_pool is not None, "Pools not started"
    with ro_pool.connection() as conn:
        yield conn
