from fastapi import APIRouter, HTTPException
from app.utils.postgres_db import find_one, find_many, update_one

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users")
def get_users(role: str = None):
    """Get list of users, optionally filtered by role"""
    if role:
        return find_many("users", {"role": role})

    return find_many("users")

@router.put("/supplier/{supplier_id}")
def update_supplier(supplier_id: str, supplier_data: dict):
    supplier = find_one("suppliers", {"id": supplier_id})
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    updated_data = dict(supplier)
    updated_data.update(supplier_data)
    update_one("suppliers", {"id": supplier_id}, supplier_data)
    return updated_data

@router.put("/po-assignment/{po_id}")
def update_po_assignment(po_id: str, assignment_data: dict):
    po = find_one("purchase_orders", {"id": po_id})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    po["procurement_specialist_id"] = assignment_data.get("procurement_specialist_id")
    po["supplier_id"] = assignment_data.get("supplier_id")

    update_one("purchase_orders", {"id": po_id}, {
        "procurement_specialist_id": po["procurement_specialist_id"],
        "supplier_id": po["supplier_id"],
    })

    return po