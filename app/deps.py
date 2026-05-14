from typing import Annotated
from fastapi import Depends, Header, HTTPException, status

from .db import app_conn
from .security import decode_access_token


def _bearer(token: str | None) -> str:
    if not token or not token.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return token.split(" ", 1)[1].strip()


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    token = _bearer(authorization)
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user_id = int(payload["sub"])
    with app_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, full_name, role, is_active, created_at FROM app.users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if not row or not row[4]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer active")
    return {
        "id": row[0],
        "email": row[1],
        "full_name": row[2],
        "role": row[3],
        "is_active": row[4],
        "created_at": row[5],
    }


CurrentUser = Annotated[dict, Depends(current_user)]
