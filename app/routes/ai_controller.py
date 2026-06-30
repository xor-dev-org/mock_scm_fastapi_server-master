from fastapi import APIRouter, HTTPException

from app.dto.ai_dto import SqlAgentQueryRequest
from app.services.sql_agent_service import SQLAgentService

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/sql-query")
def ask_sql_agent(payload: SqlAgentQueryRequest):
    result = SQLAgentService().ask(payload.query)

    if "error" in result:
        status_code = 503 if not SQLAgentService().enabled else 500
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result