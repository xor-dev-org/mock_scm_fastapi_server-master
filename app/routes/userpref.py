from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Tuple

from app.utils.json_db import read_json, write_json

router = APIRouter(prefix="/user-pref", tags=["User Preference"])

class UpdatePinnedRowsRequest(BaseModel):
    user_id: str
    pinned_rows: List[str]


def _find_user_record(user_id: str) -> Tuple[dict, str, str]:
    """Search suppliers and users for a matching user id.

    Returns the record, file name, and record key field.
    """
    suppliers = read_json("suppliers.json")
    for user in suppliers:
        if user.get("id") == user_id:
            return user, "suppliers.json", "suppliers"

    users = read_json("users.json")
    for user in users:
        if user.get("id") == user_id:
            return user, "users.json", "users"

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
    # Update record in suppliers.json or users.json, whichever contains the user.
    try:
        user, file_name, record_type = _find_user_record(req.user_id)
    except HTTPException:
        raise

    data = read_json(file_name)
    updated = False

    for record in data:
        if record.get("id") == req.user_id:
            record["pinned_rows"] = req.pinned_rows
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    write_json(file_name, data)

    return {
        "message": "Pinned rows updated successfully",
        "user_id": req.user_id,
        "pinned_rows": req.pinned_rows,
    }
