from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError

from app.dto.ai_dto import SqlAgentQueryRequest
from app.middleware.access_control import BlockedUsers
from app.services.sql_agent_service import SQLAgentService
from app.utils.auth import decode_token, extract_bearer_token

router = APIRouter(prefix="/ai", tags=["AI"])

blocked_users = BlockedUsers([
    "bmcneal@myersaubrey.com", "pwi@boers.nl", 
    "ps10@mockscm.com", "ps11@mockscm.com", "ps12@mockscm.com",
])

def _current_user(authorization: str) -> Dict:
    try:
        token = extract_bearer_token(authorization)
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user_id = payload.get("sub")
    role = payload.get("role")

    if not user_id or not role:
        raise HTTPException(status_code=401, detail="Token missing required fields")

    return {
        "id": user_id,
        "name": payload.get("name", ""),
        "email": payload.get("email", ""),
        "role": role,
        "supplier_number": payload.get("supplier_number"),
        "supplier_msid": payload.get("supplier_msid"),
    }


@router.post("/sql-query")
def ask_sql_agent(payload: SqlAgentQueryRequest, authorization: Optional[str] = Header(default=None), current_user: dict = Depends(blocked_users)):
    # if authorization is not None:
    #     current_user = _current_user(authorization)
    #     role = current_user.get("role")
    #     user_id = current_user.get("id")
    #     email = current_user.get("email")
    #     supplier_msid = current_user.get("supplier_msid")
    #     supplier_number = current_user.get("supplier_number")
    # else:
    #     raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # result = SQLAgentService().ask(
    #     payload.query,
    #     role=role or "ADMIN",
    #     supplier_msid=supplier_msid,
    # )

    # if "error" in result:
    #     status_code = 503 if not SQLAgentService().enabled else 500
    #     raise HTTPException(status_code=status_code, detail=result["error"])

    # return result
    raise HTTPException(status_code=503, detail="SQL Agent service is currently unavailable.")