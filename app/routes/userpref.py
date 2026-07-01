from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List

from app.db.models import User
from app.db.session import SessionLocal

router = APIRouter(prefix="/user-pref", tags=["User Preference"])


PIN_FIELD_MAP = {
    "po": "pinned_rows",
    "po_to_review": "pinned_po_to_review_line_items",
    "mrp_exception": "pinned_mrp_exception_line_items",
    "po_details_lines": "pinned_po_details_lines",
    "po_details_documents": "pinned_po_details_documents",
}


class UpdatePinnedRowsRequest(BaseModel):
    user_id: str
    pinned_rows: List[str]
    pin_type: str = "po"

class UpdateGridColumnVisibilityRequest(BaseModel):
    user_id: str
    grid_key: str
    column_visibility_model: Dict[str, bool]


class PinnedRowsResponse(BaseModel):
    user_id: str
    pin_type: str
    pinned_rows: List[str]


class BatchPinnedRowsResponse(BaseModel):
    user_id: str
    pinned_rows: Dict[str, List[str]]

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
    if pin_type == "po_details_lines":
        return "pinned_po_details_lines"
    if pin_type == "po_details_documents":
        return "pinned_po_details_documents"
    return None


def _get_pinned_rows_for_user(user: User, pin_type: str) -> List[str]:
    if pin_type == "po":
        return list(user.pinned_rows or [])

    metadata = dict(user.metadata_json or {})
    meta_key = _get_pin_metadata_key(pin_type)
    if not meta_key:
        return []
    return list(metadata.get(meta_key, []))


def _normalize_pinned_rows(pinned_rows: List[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for row_id in pinned_rows or []:
        value = str(row_id).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _set_pinned_rows_for_user(user: User, pin_type: str, pinned_rows: List[str]) -> None:
    normalized_rows = _normalize_pinned_rows(pinned_rows)

    if pin_type == "po":
        user.pinned_rows = normalized_rows
        return

    metadata = dict(user.metadata_json or {})
    meta_key = _get_pin_metadata_key(pin_type)
    if meta_key:
        metadata[meta_key] = normalized_rows
        user.metadata_json = metadata



@router.get("/pinned-rows")
def get_pinned_rows(
    user_id: str,
    pin_type: str = Query("po", description="Pin type: po, po_to_review, mrp_exception, po_details_lines, po_details_documents"),
)-> PinnedRowsResponse:
    _get_pin_field(pin_type)
    user = _find_user_or_404(user_id)

    return PinnedRowsResponse(
        user_id=user_id,
        pin_type=pin_type,
        pinned_rows=_get_pinned_rows_for_user(user, pin_type),
    )


@router.get("/pinned-rows/batch")
def get_pinned_rows_batch(
    user_id: str,
    pin_types: List[str] = Query(
        ["po", "po_to_review", "mrp_exception"],
        description="Pin types to fetch",
    ),
) -> BatchPinnedRowsResponse:
    normalized_types: List[str] = []
    seen_types = set()
    for pin_type in pin_types:
        _get_pin_field(pin_type)
        if pin_type not in seen_types:
            normalized_types.append(pin_type)
            seen_types.add(pin_type)

    user = _find_user_or_404(user_id)

    return BatchPinnedRowsResponse(
        user_id=user_id,
        pinned_rows={
            pin_type: _get_pinned_rows_for_user(user, pin_type)
            for pin_type in normalized_types
        },
    )


@router.put("/pinned-rows")
def update_pinned_rows(req: UpdatePinnedRowsRequest):
    _get_pin_field(req.pin_type)

    session = SessionLocal()
    normalized_rows = _normalize_pinned_rows(req.pinned_rows)
    try:
        user = session.get(User, req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        _set_pinned_rows_for_user(user, req.pin_type, normalized_rows)
        session.add(user)
        session.commit()
    finally:
        session.close()

    return {
        "message": "Pinned rows updated successfully",
        "user_id": req.user_id,
        "pin_type": req.pin_type,
        "pinned_rows": normalized_rows,
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

@router.get("/grid-column-visibility")
def get_grid_column_visibility(user_id: str, grid_key: str):
    if not grid_key.strip():
        raise HTTPException(status_code=400, detail="grid_key is required")

    user = _find_user_or_404(user_id)

    metadata = dict(user.metadata_json or {})
    grid_visibility_map = dict(metadata.get("grid_column_visibility") or {})

    return {
        "user_id": user_id,
        "grid_key": grid_key,
        "column_visibility_model": dict(grid_visibility_map.get(grid_key) or {}),
    }


@router.put("/grid-column-visibility")
def update_grid_column_visibility(req: UpdateGridColumnVisibilityRequest):
    if not req.grid_key.strip():
        raise HTTPException(status_code=400, detail="grid_key is required")

    session = SessionLocal()
    try:
        user = session.get(User, req.user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        metadata = dict(user.metadata_json or {})
        grid_visibility_map = dict(metadata.get("grid_column_visibility") or {})

        grid_visibility_map[req.grid_key] = dict(req.column_visibility_model)
        metadata["grid_column_visibility"] = grid_visibility_map

        user.metadata_json = metadata

        session.add(user)
        session.commit()

        return {
            "message": "Grid column visibility updated successfully",
            "user_id": req.user_id,
            "grid_key": req.grid_key,
            "column_visibility_model": req.column_visibility_model,
        }
    finally:
        session.close()