from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List

from app.utils.mongo_db import find_one, update_one
from app.db.models import User
from app.db.session import SessionLocal

router = APIRouter(prefix="/user-pref", tags=["User Preference"])


PIN_FIELD_MAP = {
    "po": "pinned_rows",
    "po_to_review": "pinned_po_to_review_line_items",
    "mrp_exception": "pinned_mrp_exception_line_items",
}


class UpdatePinnedRowsRequest(BaseModel):
    user_id: str
    pinned_rows: List[str]
    pin_type: str = "po"


def _get_pin_field(pin_type: str) -> str:
    field_name = PIN_FIELD_MAP.get(pin_type)

    if not field_name:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pin_type: {pin_type}. Allowed values are: {list(PIN_FIELD_MAP.keys())}",
        )

    return field_name


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
def get_pinned_rows(
    user_id: str,
    pin_type: str = Query("po", description="Pin type: po, po_to_review, mrp_exception"),
):
    field_name = _get_pin_field(pin_type)

    user, _, _ = _find_user_record(user_id)

    return {
        "user_id": user_id,
        "pin_type": pin_type,
        "pinned_rows": user.get(field_name, []),
    }


@router.put("/pinned-rows")
def update_pinned_rows(req: UpdatePinnedRowsRequest):
    field_name = _get_pin_field(req.pin_type)

    try:
        user, collection_name, _ = _find_user_record(req.user_id)
    except HTTPException:
        raise

    update_count = update_one(
        collection_name,
        {"id": req.user_id},
        {field_name: req.pinned_rows},
    )

    if update_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "message": "Pinned rows updated successfully",
        "user_id": req.user_id,
        "pin_type": req.pin_type,
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
