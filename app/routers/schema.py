from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ..config import get_settings
from ..db import app_conn
from ..deps import CurrentUser
from ..semantic import load_semantic_model, load_semantic_text

router = APIRouter(prefix="/api", tags=["schema"])
_settings = get_settings()


@router.get("/schema")
def schema_overview(user: CurrentUser) -> dict:
    schema = _settings.SCHEMA_NAME
    with app_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, obj_description(
                (quote_ident(table_schema)||'.'||quote_ident(table_name))::regclass, 'pg_class'
            ) AS table_comment
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (schema,),
        )
        tables = [{"name": r[0], "comment": r[1]} for r in cur.fetchall()]

        cur.execute(
            """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
            """,
            (schema,),
        )
        by_table: dict[str, list[dict]] = {}
        for t, c, dt, nul in cur.fetchall():
            by_table.setdefault(t, []).append({"name": c, "type": dt, "nullable": nul == "YES"})

        cur.execute(
            """
            SELECT relname, n_live_tup
            FROM pg_stat_user_tables
            WHERE schemaname = %s
            """,
            (schema,),
        )
        counts = {r[0]: int(r[1]) for r in cur.fetchall()}

    for t in tables:
        t["columns"] = by_table.get(t["name"], [])
        t["approx_row_count"] = counts.get(t["name"])

    return {"schema": schema, "tables": tables}


@router.get("/semantic")
def semantic(user: CurrentUser) -> dict:
    return load_semantic_model()


@router.get("/semantic/raw", response_class=PlainTextResponse)
def semantic_raw(user: CurrentUser) -> str:
    return load_semantic_text()
