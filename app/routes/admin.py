from fastapi import APIRouter, HTTPException

from app.db.models import User
from app.db.session import SessionLocal
from app.utils.postgres_db import find_relational_purchase_order, replace_relational_purchase_order

router = APIRouter(prefix="/admin", tags=["Admin"])


def _serialize_user(row: User) -> dict:
    payload = dict(row.metadata_json or {})
    payload.update(
        {
            "id": row.id,
            "name": row.name,
            "email": row.email,
            "role": row.role,
            "password": row.password,
            "supplier_number": row.supplier_number,
            "phone": row.phone,
            "address": row.address,
            "site": row.site,
            "supplier_msid": row.supplier_msid,
            "pinned_rows": row.pinned_rows or [],
            "line_pinned_rows": row.line_pinned_rows or [],
        }
    )
    return payload

@router.get("/users")
def get_users(role: str = None):
    """Get list of users, optionally filtered by role"""
    session = SessionLocal()
    try:
        query = session.query(User)
        if role:
            query = query.filter(User.role == role)
        else:
            query = query.filter(User.role != "SUPPLIER")

        rows = query.all()
        return [_serialize_user(row) for row in rows]
    finally:
        session.close()

@router.put("/supplier/{supplier_id}")
def update_supplier(supplier_id: str, supplier_data: dict):
    session = SessionLocal()
    try:
        supplier = session.get(User, supplier_id)
        if not supplier or supplier.role != "SUPPLIER":
            raise HTTPException(status_code=404, detail="Supplier not found")

        for key, value in supplier_data.items():
            if hasattr(supplier, key):
                setattr(supplier, key, value)
            else:
                metadata = dict(supplier.metadata_json or {})
                metadata[key] = value
                supplier.metadata_json = metadata

        session.add(supplier)
        session.commit()
        session.refresh(supplier)
        return _serialize_user(supplier)
    finally:
        session.close()

@router.put("/po-assignment/{po_id}")
def update_po_assignment(po_id: str, assignment_data: dict):
    po = find_relational_purchase_order(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    po["procurement_specialist_id"] = assignment_data.get("procurement_specialist_id")
    po["supplier_id"] = assignment_data.get("supplier_id")

    persisted = replace_relational_purchase_order(
        po_id,
        {
            **po,
            "procurement_specialist_id": po["procurement_specialist_id"],
            "supplier_id": po["supplier_id"],
        },
    )
    if not persisted:
        raise HTTPException(status_code=500, detail="Failed to update PO assignment")

    return persisted