from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    row_limit: Optional[int] = None
    execute: bool = True


class AskResponse(BaseModel):
    question: str
    sql: str
    reasoning: str
    clarification: Optional[str] = None
    refused: bool = False
    refusal_reason: Optional[str] = None
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int = 0
    truncated: bool = False
    execution_ms: Optional[int] = None
    chart_suggestion: Optional[dict[str, Any]] = None
    explanation: Optional[str] = None
    validation: dict[str, Any] = {}
    audit_id: Optional[int] = None


class ExecuteRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)
    row_limit: Optional[int] = None


class HistoryItem(BaseModel):
    id: int
    question: str
    sql: Optional[str]
    status: str
    safety_status: str
    row_count: Optional[int]
    execution_ms: Optional[int]
    created_at: datetime


TokenResponse.model_rebuild()
