from fastapi import APIRouter, HTTPException
from app.utils.json_db import read_json, write_json

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users")
def get_users(role: str = None):
    """Get list of users, optionally filtered by role"""
    users = read_json("users.json")
    
    if role:
        users = [u for u in users if u.get("role") == role]
    
    return users

@router.put("/supplier/{supplier_id}")
def update_supplier(supplier_id: str, supplier_data: dict):
    suppliers = read_json("suppliers.json")

    for index, supplier in enumerate(suppliers):
        if supplier["id"] == supplier_id:
            suppliers[index].update(supplier_data)
            write_json("suppliers.json", suppliers)
            return suppliers[index]

    raise HTTPException(status_code=404, detail="Supplier not found")

@router.put("/po-assignment/{po_id}")
def update_po_assignment(po_id: str, assignment_data: dict):
    pos = read_json("purchase_orders.json")

    for index, po in enumerate(pos):
        if po["id"] == po_id:
            pos[index]["procurement_specialist_id"] = assignment_data.get("procurement_specialist_id")
            pos[index]["supplier_id"] = assignment_data.get("supplier_id")

            write_json("purchase_orders.json", pos)

            return pos[index]

    raise HTTPException(status_code=404, detail="PO not found")