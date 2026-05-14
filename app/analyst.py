"""Orchestrates the ask flow: generate -> validate -> execute -> explain.

All steps emit audit records so that an admin can review what was asked,
generated, validated, and executed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import psycopg

from .config import get_settings
from .db import app_conn, ro_conn
from .llm import explain_result, generate_sql, suggest_chart
from .sql_validator import enforce_limit, validate_sql

log = logging.getLogger(__name__)
_settings = get_settings()


def _insert_audit(
    user: dict,
    question: str,
    sql: str | None,
    validation_status: str,
    safety_status: str,
    safety_reason: str | None,
    execution_status: str,
    execution_error: str | None,
    row_count: int | None,
    execution_ms: int | None,
) -> int:
    with app_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.audit_log
                (user_id, user_email, user_role, question, generated_sql,
                 validation_status, safety_status, safety_reason,
                 execution_status, execution_error, row_count, execution_ms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                user["id"], user["email"], user["role"], question, sql,
                validation_status, safety_status, safety_reason,
                execution_status, execution_error, row_count, execution_ms,
            ),
        )
        audit_id = cur.fetchone()[0]
        conn.commit()
    return audit_id


def _run_query(sql: str, limit: int) -> tuple[list[str], list[list[Any]], int, bool]:
    enforced = enforce_limit(sql, limit + 1)  # +1 to detect truncation
    started = time.perf_counter()
    with ro_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{_settings.QUERY_TIMEOUT_SECONDS}s'")
            cur.execute(enforced)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    truncated = len(rows) > limit
    if truncated:
        rows = rows[:limit]
    # Normalize values for JSON serialization (Decimal, dates handled by FastAPI's jsonable encoder).
    return cols, [list(r) for r in rows], elapsed_ms, truncated


def ask(user: dict, question: str, row_limit: int | None, execute: bool) -> dict:
    limit = min(row_limit or _settings.QUERY_DEFAULT_LIMIT, _settings.QUERY_MAX_LIMIT)

    result: dict[str, Any] = {
        "question": question,
        "sql": "",
        "reasoning": "",
        "clarification": None,
        "refused": False,
        "refusal_reason": None,
        "columns": [],
        "rows": [],
        "row_count": 0,
        "truncated": False,
        "execution_ms": None,
        "chart_suggestion": None,
        "explanation": None,
        "validation": {},
        "audit_id": None,
    }

    llm = generate_sql(question, user_role=user["role"])
    result["sql"] = llm.sql
    result["reasoning"] = llm.reasoning
    result["clarification"] = llm.clarification
    result["refused"] = llm.refused
    result["refusal_reason"] = llm.refusal_reason

    if llm.refused or not llm.sql:
        result["audit_id"] = _insert_audit(
            user, question, llm.sql or None,
            validation_status="refused" if llm.refused else "invalid",
            safety_status="refused" if llm.refused else "blocked",
            safety_reason=llm.refusal_reason or llm.clarification or "Empty SQL",
            execution_status="skipped",
            execution_error=None, row_count=None, execution_ms=None,
        )
        return result

    validation = validate_sql(llm.sql)
    result["validation"] = validation.to_dict()

    if not validation.valid:
        result["refused"] = True
        result["refusal_reason"] = validation.reason
        result["audit_id"] = _insert_audit(
            user, question, llm.sql,
            validation_status="invalid", safety_status="blocked",
            safety_reason=validation.reason,
            execution_status="skipped",
            execution_error=None, row_count=None, execution_ms=None,
        )
        return result

    if not execute:
        result["audit_id"] = _insert_audit(
            user, question, llm.sql,
            validation_status="valid", safety_status="safe",
            safety_reason=None,
            execution_status="skipped",
            execution_error=None, row_count=None, execution_ms=None,
        )
        return result

    try:
        cols, rows, elapsed_ms, truncated = _run_query(llm.sql, limit)
        result["columns"] = cols
        result["rows"] = rows
        result["row_count"] = len(rows)
        result["truncated"] = truncated
        result["execution_ms"] = elapsed_ms
        result["chart_suggestion"] = suggest_chart(cols, rows)
        try:
            result["explanation"] = explain_result(question, llm.sql, cols, rows)
        except Exception:
            log.exception("Explanation step failed (non-fatal)")
        result["audit_id"] = _insert_audit(
            user, question, llm.sql,
            validation_status="valid", safety_status="safe", safety_reason=None,
            execution_status="success", execution_error=None,
            row_count=len(rows), execution_ms=elapsed_ms,
        )
    except psycopg.Error as exc:
        result["refused"] = False
        result["refusal_reason"] = None
        result["validation"] = {**result["validation"], "execution_error": str(exc)}
        result["audit_id"] = _insert_audit(
            user, question, llm.sql,
            validation_status="valid", safety_status="safe", safety_reason=None,
            execution_status="error", execution_error=str(exc),
            row_count=None, execution_ms=None,
        )
        # Re-raise as a clean message via the router layer.
        raise

    return result


def execute_sql(user: dict, sql: str, row_limit: int | None) -> dict:
    limit = min(row_limit or _settings.QUERY_DEFAULT_LIMIT, _settings.QUERY_MAX_LIMIT)
    validation = validate_sql(sql)
    if not validation.valid:
        _insert_audit(
            user, "[direct-execute]", sql,
            validation_status="invalid", safety_status="blocked",
            safety_reason=validation.reason,
            execution_status="skipped",
            execution_error=None, row_count=None, execution_ms=None,
        )
        return {
            "refused": True,
            "refusal_reason": validation.reason,
            "validation": validation.to_dict(),
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

    try:
        cols, rows, elapsed_ms, truncated = _run_query(sql, limit)
    except psycopg.Error as exc:
        _insert_audit(
            user, "[direct-execute]", sql,
            validation_status="valid", safety_status="safe", safety_reason=None,
            execution_status="error", execution_error=str(exc),
            row_count=None, execution_ms=None,
        )
        return {
            "refused": False,
            "refusal_reason": None,
            "execution_error": str(exc),
            "validation": validation.to_dict(),
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

    _insert_audit(
        user, "[direct-execute]", sql,
        validation_status="valid", safety_status="safe", safety_reason=None,
        execution_status="success", execution_error=None,
        row_count=len(rows), execution_ms=elapsed_ms,
    )

    return {
        "refused": False,
        "validation": validation.to_dict(),
        "columns": cols,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "execution_ms": elapsed_ms,
        "chart_suggestion": suggest_chart(cols, rows),
    }
