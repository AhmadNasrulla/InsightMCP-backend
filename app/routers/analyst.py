from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from .. import analyst as analyst_service
from ..deps import CurrentUser
from ..schemas import AskRequest, ExecuteRequest

router = APIRouter(prefix="/api/analyst", tags=["analyst"])


@router.post("/ask")
def ask(req: AskRequest, user: CurrentUser):
    try:
        result = analyst_service.ask(user, req.question, req.row_limit, req.execute)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Analyst pipeline failed: {exc}")
    return jsonable_encoder(result)


@router.post("/execute")
def execute(req: ExecuteRequest, user: CurrentUser):
    result = analyst_service.execute_sql(user, req.sql, req.row_limit)
    return jsonable_encoder(result)
