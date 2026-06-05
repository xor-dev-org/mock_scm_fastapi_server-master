from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from app.utils.json_db import read_json, write_json

router = APIRouter(prefix="/user-pref", tags=["User Preference"])

class UpdatePinnedRowsRequest(BaseModel):
    user_id: str
    pinned_rows: List[str]

@router.get("/pinned-rows")
def get_pinned_rows(user_id: str):
    users = read_json("users.json")

    for user in users:
        if user["id"] == user_id:
            return {
                "user_id": user_id,
                "pinned_rows": user.get("pinned_rows", [])
            }

    raise HTTPException(status_code=404, detail="User not found")


@router.put("/pinned-rows")
def update_pinned_rows(req: UpdatePinnedRowsRequest):
    users = read_json('users.json')
    updated = False

    for user in users:
        if user["id"] == req.user_id:
            user["pinned_rows"] = req.pinned_rows
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    print(f"Updated pinned rows for user {req.user_id}: {req.pinned_rows}")
    print(f"Updated pinned rows for user- {user}")
    write_json("users.json", users)

    return {
        "message": "Pinned rows updated successfully",
        "user_id": req.user_id,
        "pinned_rows": req.pinned_rows
    }
