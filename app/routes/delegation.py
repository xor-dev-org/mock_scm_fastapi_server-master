from fastapi import APIRouter, HTTPException
from datetime import datetime, date
import uuid

from app.db.models import Delegation
from app.db.session import SessionLocal

router = APIRouter(prefix="/delegation", tags=["Delegations"])


def _safe_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _safe_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _serialize_delegation(row: Delegation) -> dict:
    return {
        "id": row.id,
        "po_id": row.po_id,
        "po_number": row.po_number,
        "supplier_name": row.supplier_name,
        "delegated_from_id": row.delegated_from_id,
        "delegated_to_id": row.delegated_to_id,
        "role": row.role,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "status": row.status,
        "created_date": row.created_date.isoformat() if row.created_date else None,
        "total_value": row.total_value,
    }

@router.get("")
def get_delegations(
    page: int = 1,
    page_size: int = 50,
    status: str = None,
    search: str = None,
    sort_by: str = None
):
    """Get list of delegations with filters and pagination"""
    session = SessionLocal()
    try:
        delegations = [_serialize_delegation(row) for row in session.query(Delegation).all()]
    finally:
        session.close()
    
    # Status filter
    if status:
        delegations = [d for d in delegations if d["status"] == status]
    
    # Search filter (by PO number or PS name)
    if search:
        search_lower = search.lower()
        delegations = [
            d for d in delegations
            if search_lower in d.get("po_number", "").lower()
            or search_lower in d.get("delegated_to_name", "").lower()
        ]
    
    # Sorting
    if sort_by == "date_asc":
        delegations = sorted(delegations, key=lambda x: x.get("start_date", ""))
    elif sort_by == "date_desc":
        delegations = sorted(delegations, key=lambda x: x.get("start_date", ""), reverse=True)
    else:
        # Default: latest first
        delegations = sorted(delegations, key=lambda x: x.get("created_date", ""), reverse=True)
    
    total = len(delegations)
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": delegations[start:end]
    }

@router.get("/{delegation_id}")
def get_delegation(delegation_id: str):
    """Get a specific delegation by ID"""
    session = SessionLocal()
    try:
        row = session.get(Delegation, delegation_id)
    finally:
        session.close()

    delegation = _serialize_delegation(row) if row else None
    
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    
    return delegation

@router.post("")
def create_delegation(delegation_data: dict):
    """Create a new delegation"""
    row = Delegation(
        id=f"DEL-{str(uuid.uuid4()).split('-')[0].upper()}",
        po_id=delegation_data.get("po_id") or "",
        po_number=delegation_data.get("po_number"),
        supplier_name=delegation_data.get("supplier_name"),
        delegated_from_id=delegation_data.get("delegated_from_id") or "",
        delegated_to_id=delegation_data.get("delegated_to_id") or "",
        role=delegation_data.get("role"),
        start_date=_safe_date(delegation_data.get("start_date")),
        end_date=_safe_date(delegation_data.get("end_date")),
        status="DRAFT",
        total_value=delegation_data.get("total_value"),
        created_date=datetime.now(),
    )

    session = SessionLocal()
    try:
        session.add(row)
        session.commit()
        session.refresh(row)
        return _serialize_delegation(row)
    finally:
        session.close()

@router.delete("/{delegation_id}")
def delete_delegation(delegation_id: str):
    """Delete a delegation"""
    session = SessionLocal()
    try:
        row = session.get(Delegation, delegation_id)
        if not row:
            raise HTTPException(status_code=404, detail="Delegation not found")
        session.delete(row)
        session.commit()
    finally:
        session.close()

    return {"message": "Delegation removed successfully"}

@router.put("/{delegation_id}")
def update_delegation(delegation_id: str, updated_data: dict):
    """Update a delegation"""
    session = SessionLocal()
    try:
        row = session.get(Delegation, delegation_id)
        if not row:
            raise HTTPException(status_code=404, detail="Delegation not found")

        for key, value in updated_data.items():
            if key in {"start_date", "end_date"}:
                setattr(row, key, _safe_date(value))
                continue
            if key == "created_date":
                row.created_date = _safe_datetime(value)
                continue
            if hasattr(row, key):
                setattr(row, key, value)

        session.add(row)
        session.commit()
        session.refresh(row)
        return _serialize_delegation(row)
    finally:
        session.close()
