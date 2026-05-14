from fastapi import APIRouter, HTTPException, status
from psycopg.errors import UniqueViolation

from ..db import app_conn
from ..deps import CurrentUser
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _row_to_user(row) -> UserOut:
    return UserOut(
        id=row[0], email=row[1], full_name=row[2], role=row[3], created_at=row[4]
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> TokenResponse:
    pw_hash = hash_password(payload.password)
    with app_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app.users (email, full_name, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, email, full_name, role, created_at
                    """,
                    (payload.email.lower(), payload.full_name.strip(), pw_hash),
                )
                row = cur.fetchone()
            conn.commit()
        except UniqueViolation:
            conn.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    user = _row_to_user(row)
    token = create_access_token(str(user.id), {"email": user.email, "role": user.role})
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    with app_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, full_name, role, created_at, password_hash, is_active
                FROM app.users WHERE email = %s
                """,
                (payload.email.lower(),),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

        user_id, email, full_name, role, created_at, password_hash, is_active = row
        if not is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled.")
        if not verify_password(payload.password, password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

        with conn.cursor() as cur:
            cur.execute("UPDATE app.users SET last_login_at = NOW() WHERE id = %s", (user_id,))
        conn.commit()

    user = UserOut(id=user_id, email=email, full_name=full_name, role=role, created_at=created_at)
    token = create_access_token(str(user.id), {"email": user.email, "role": user.role})
    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut(
        id=user["id"], email=user["email"], full_name=user["full_name"],
        role=user["role"], created_at=user["created_at"],
    )
