from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from app.db.models import User
from app.db.session import SessionLocal

router = APIRouter(prefix="/user-pref", tags=["User Preference"])

class UpdatePinnedRowsRequest(BaseModel):
    user_id: str
    pinned_rows: List[str]


class UpdateLinePinnedRowsRequest(BaseModel):
    user_id: str
    line_pinned_rows: List[str]


def _find_user_or_404(user_id: str) -> User:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    finally:
        session.close()


@router.get("/pinned-rows")
def get_pinned_rows(user_id: str):
    user = _find_user_or_404(user_id)
    return {
        "user_id": user_id,
        "pinned_rows": list(user.pinned_rows or []),
    }


@router.put("/pinned-rows")
def update_pinned_rows(req: UpdatePinnedRowsRequest):
    session = SessionLocal()
    try:
        user = session.get(User, req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.pinned_rows = list(req.pinned_rows)
        session.add(user)
        session.commit()
    finally:
        session.close()

    return {
        "message": "Pinned rows updated successfully",
        "user_id": req.user_id,
        "pinned_rows": req.pinned_rows,
    }


@router.get("/line-pinned-rows")
def get_line_pinned_rows(user_id: str):
    user = _find_user_or_404(user_id)
    return {
        "user_id": user_id,
        "line_pinned_rows": list(user.line_pinned_rows or []),
    }


@router.put("/line-pinned-rows")
def update_line_pinned_rows(req: UpdateLinePinnedRowsRequest):
    session = SessionLocal()
    try:
        user = session.get(User, req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.line_pinned_rows = list(req.line_pinned_rows)
        session.add(user)
        session.commit()
    finally:
        session.close()

    return {
        "message": "Line pinned rows updated successfully",
        "user_id": req.user_id,
        "line_pinned_rows": req.line_pinned_rows,
    }
