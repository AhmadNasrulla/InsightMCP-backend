from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from ..db import app_conn
from ..deps import CurrentUser

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    with app_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, question, generated_sql, execution_status, safety_status,
                   row_count, execution_ms, created_at
            FROM app.audit_log
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (user["id"], limit, offset),
        )
        rows = cur.fetchall()

    items = [
        {
            "id": r[0],
            "question": r[1],
            "sql": r[2],
            "status": r[3],
            "safety_status": r[4],
            "row_count": r[5],
            "execution_ms": r[6],
            "created_at": r[7],
        }
        for r in rows
    ]
    return jsonable_encoder({"items": items})


@router.get("/{audit_id}")
def get_history_item(audit_id: int, user: CurrentUser):
    with app_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, question, generated_sql, validation_status, safety_status, safety_reason,
                   execution_status, execution_error, row_count, execution_ms, created_at
            FROM app.audit_log
            WHERE id = %s AND user_id = %s
            """,
            (audit_id, user["id"]),
        )
        row = cur.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    return jsonable_encoder({
        "id": row[0],
        "question": row[1],
        "sql": row[2],
        "validation_status": row[3],
        "safety_status": row[4],
        "safety_reason": row[5],
        "execution_status": row[6],
        "execution_error": row[7],
        "row_count": row[8],
        "execution_ms": row[9],
        "created_at": row[10],
    })
