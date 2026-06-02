from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from app.utils.json_db import read_json, write_json

router = APIRouter(prefix="/user-pref", tags=["User Preference"])

class UpdatePinnedColumnsRequest(BaseModel):
    user_id: str
    pinned_columns: List[str]

@router.get("/pinned-columns")
def get_pinned_columns(user_id: str):
    users = read_json("users.json")

    for user in users:
        if user["id"] == user_id:
            return {
                "user_id": user_id,
                "pinned_columns": user.get("pinned_columns", [])
            }

    raise HTTPException(status_code=404, detail="User not found")


@router.put("/pinned-columns")
def update_pinned_columns(req: UpdatePinnedColumnsRequest):
    users = read_json()
    updated = False

    for user in users:
        if user["id"] == req.user_id:
            user["pinned_columns"] = req.pinned_columns
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    write_json(users)

    return {
        "message": "Pinned columns updated successfully",
        "user_id": req.user_id,
        "pinned_columns": req.pinned_columns
    }