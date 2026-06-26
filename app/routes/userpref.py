from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List

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


def _get_pin_metadata_key(pin_type: str) -> str | None:
    if pin_type == "po_to_review":
        return "pinned_po_to_review_line_items"
    if pin_type == "mrp_exception":
        return "pinned_mrp_exception_line_items"
    return None


def _get_pinned_rows_for_user(user: User, pin_type: str) -> List[str]:
    if pin_type == "po":
        return list(user.pinned_rows or [])

    metadata = dict(user.metadata_json or {})
    meta_key = _get_pin_metadata_key(pin_type)
    if not meta_key:
        return []
    return list(metadata.get(meta_key, []))


def _set_pinned_rows_for_user(user: User, pin_type: str, pinned_rows: List[str]) -> None:
    if pin_type == "po":
        user.pinned_rows = list(pinned_rows)
        return

    metadata = dict(user.metadata_json or {})
    meta_key = _get_pin_metadata_key(pin_type)
    if meta_key:
        metadata[meta_key] = list(pinned_rows)
        user.metadata_json = metadata



@router.get("/pinned-rows")
def get_pinned_rows(
    user_id: str,
    pin_type: str = Query("po", description="Pin type: po, po_to_review, mrp_exception"),
):
    _get_pin_field(pin_type)
    user = _find_user_or_404(user_id)

    return {
        "user_id": user_id,
        "pin_type": pin_type,
        "pinned_rows": _get_pinned_rows_for_user(user, pin_type),
    }


@router.put("/pinned-rows")
def update_pinned_rows(req: UpdatePinnedRowsRequest):
    _get_pin_field(req.pin_type)

    session = SessionLocal()
    try:
        user = session.get(User, req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        _set_pinned_rows_for_user(user, req.pin_type, req.pinned_rows)
        session.add(user)
        session.commit()
    finally:
        session.close()

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
