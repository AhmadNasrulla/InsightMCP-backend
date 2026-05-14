"""Standalone MCP server exposing the warehouse as resources, tools, and prompts.

Run with: python mcp_server.py
This is independent from the FastAPI app and uses the same read-only role.
"""

from __future__ import annotations

import json
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.analyst import _run_query as run_query
from app.config import get_settings
from app.db import app_conn, ro_conn, startup_pools
from app.llm import explain_result, generate_sql, suggest_chart
from app.semantic import load_semantic_text, load_semantic_model
from app.sql_validator import validate_sql

_settings = get_settings()
mcp = FastMCP("retail-sql-analyst")


@mcp.resource("retail://schema/overview")
def schema_overview() -> str:
    schema = _settings.SCHEMA_NAME
    with app_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema=%s AND table_type='BASE TABLE'
            ORDER BY table_name
            """,
            (schema,),
        )
        tables = [r[0] for r in cur.fetchall()]
        out: dict[str, Any] = {"schema": schema, "tables": {}}
        for t in tables:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema=%s AND table_name=%s
                ORDER BY ordinal_position
                """,
                (schema, t),
            )
            out["tables"][t] = [
                {"name": c, "type": dt, "nullable": nul == "YES"}
                for c, dt, nul in cur.fetchall()
            ]
    return json.dumps(out, indent=2)


@mcp.resource("retail://semantic/model")
def semantic_model() -> str:
    return load_semantic_text()


@mcp.tool()
def profile_table(table_name: str) -> dict:
    """Return row count and sample column statistics for an allowed warehouse table."""
    allow = set(load_semantic_model().get("tables", {}).keys())
    if table_name not in allow:
        return {"error": f"Table '{table_name}' is not in the semantic allow-list."}
    with ro_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM retail_dw.{table_name}")
        count = cur.fetchone()[0]
        cur.execute(f"SELECT * FROM retail_dw.{table_name} LIMIT 5")
        cols = [d[0] for d in cur.description]
        sample = [list(r) for r in cur.fetchall()]
    return {"table": table_name, "row_count": count, "columns": cols, "sample_rows": sample}


@mcp.tool()
def validate_sql_tool(sql: str) -> dict:
    """Validate a SQL statement against the read-only allow-list."""
    return validate_sql(sql).to_dict()


@mcp.tool()
def run_readonly_query(sql: str, row_limit: int = 100) -> dict:
    """Validate and execute a read-only SQL query against the warehouse."""
    v = validate_sql(sql)
    if not v.valid:
        return {"error": v.reason, "validation": v.to_dict()}
    cols, rows, elapsed_ms, truncated = run_query(sql, min(row_limit, _settings.QUERY_MAX_LIMIT))
    return {
        "columns": cols, "rows": rows, "row_count": len(rows),
        "truncated": truncated, "execution_ms": elapsed_ms,
    }


@mcp.tool()
def generate_sql_tool(question: str, role: str = "analyst") -> dict:
    """Generate a safe SELECT SQL statement for a business question."""
    out = generate_sql(question, role)
    return {
        "sql": out.sql, "reasoning": out.reasoning,
        "clarification": out.clarification,
        "refused": out.refused, "refusal_reason": out.refusal_reason,
    }


@mcp.tool()
def explain_result_tool(question: str, sql: str, columns: list[str], rows: list[list[Any]]) -> dict:
    """Produce a short business explanation of a query result."""
    text = explain_result(question, sql, columns, rows)
    return {"explanation": text}


@mcp.tool()
def suggest_chart_tool(columns: list[str], rows: list[list[Any]]) -> dict:
    """Recommend a chart type based on result shape."""
    return suggest_chart(columns, rows)


@mcp.prompt()
def analyst_system_prompt() -> str:
    return (
        "You are a careful retail data analyst. Use the semantic model "
        "(resource retail://semantic/model). Generate safe SELECT-only SQL. "
        "Never invent values. Ask one clarification when ambiguous. Explain "
        "assumptions and filters in clear business language."
    )


if __name__ == "__main__":
    startup_pools()
    mcp.run()
