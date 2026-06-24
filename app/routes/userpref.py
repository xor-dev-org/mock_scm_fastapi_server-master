from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Tuple

from app.utils.postgres_db import find_one, query_items, update_one

router = APIRouter(prefix="/user-pref", tags=["User Preference"])

class UpdatePinnedRowsRequest(BaseModel):
    user_id: str
    pinned_rows: List[str]


class UpdateLinePinnedRowsRequest(BaseModel):
    user_id: str
    line_pinned_rows: List[str]


def _find_user_record(user_id: str) -> Tuple[dict, str, str]:
    """Search suppliers and users for a matching user id.

    Returns the record, collection name, and record key field.
    """
    user = find_one("suppliers", {"id": user_id})
    if user:
        return user, "suppliers", "suppliers"

    user = find_one("users", {"id": user_id})
    if user:
        return user, "users", "users"

    raise HTTPException(status_code=404, detail="User not found")


@router.get("/pinned-rows")
def get_pinned_rows(user_id: str):
    user, _, _ = _find_user_record(user_id)
    return {
        "user_id": user_id,
        "pinned_rows": user.get("pinned_rows", []),
    }


@router.put("/pinned-rows")
def update_pinned_rows(req: UpdatePinnedRowsRequest):
    try:
        user, collection_name, _ = _find_user_record(req.user_id)
    except HTTPException:
        raise

    update_count = update_one(collection_name, {"id": req.user_id}, {"pinned_rows": req.pinned_rows})
    if update_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "Pinned rows updated successfully",
        "user_id": req.user_id,
        "pinned_rows": req.pinned_rows,
    }


@router.get("/line-pinned-rows")
def get_line_pinned_rows(user_id: str):
    user, _, _ = _find_user_record(user_id)
    return {
        "user_id": user_id,
        "line_pinned_rows": user.get("line_pinned_rows", []),
    }


@router.put("/line-pinned-rows")
def update_line_pinned_rows(req: UpdateLinePinnedRowsRequest):
    try:
        user, collection_name, _ = _find_user_record(req.user_id)
    except HTTPException:
        raise

    update_count = update_one(collection_name, {"id": req.user_id}, {"line_pinned_rows": req.line_pinned_rows})
    if update_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "Line pinned rows updated successfully",
        "user_id": req.user_id,
        "line_pinned_rows": req.line_pinned_rows,
    }
