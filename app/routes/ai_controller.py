from fastapi import APIRouter, Depends, HTTPException

from app.dto.ai_dto import SqlAgentQueryRequest
from app.middleware.access_control import BlockedUsers
from app.services.sql_agent_service import SQLAgentService

router = APIRouter(prefix="/ai", tags=["AI"])

blocked_users = BlockedUsers([
    "bmcneal@myersaubrey.com", "pwi@boers.nl", "sydney.shaw@morganplc.com", 
    "ps10@mockscm.com", "ps11@mockscm.com", "ps12@mockscm.com",
])


@router.post("/sql-query")
def ask_sql_agent(payload: SqlAgentQueryRequest, current_user: dict = Depends(blocked_users)):
    result = SQLAgentService().ask(payload.query)

    if "error" in result:
        status_code = 503 if not SQLAgentService().enabled else 500
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result