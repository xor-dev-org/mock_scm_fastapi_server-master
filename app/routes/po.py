from fastapi import APIRouter, Query, HTTPException
from app.utils.json_db import read_json, write_json

router = APIRouter(prefix="/po", tags=["Purchase Orders"])

@router.get("")
def get_pos(
    page: int = 1,
    page_size: int = 10,
    status: str = None,
    supplier_id: str = None,
    procurement_specialist_id: str = None,
    sort_by: str = None,
    search: str = None
):
    pos = read_json("purchase_orders.json")
    print(f"Status filtering: {status}")
    if status:
        pos = [p for p in pos if p["status"] == status]
        print(f"Filtered by status: {len(pos)} POs found")

    if supplier_id:
        pos = [p for p in pos if p["supplier_id"] == supplier_id]

    if procurement_specialist_id:
        pos = [
            p for p in pos
            if p["procurement_specialist_id"] == procurement_specialist_id
        ]

    # Search filter
    if search:
        search_lower = search.lower()
        pos = [
            p for p in pos
            if search_lower in p.get("po_number", "").lower()
            or search_lower in p.get("supplier_name", "").lower()
        ]

    # Sorting
    if sort_by == "delivery_date_asc":
        pos = sorted(pos, key=lambda x: x.get("delivery_date", ""))
    elif sort_by == "delivery_date_desc":
        pos = sorted(pos, key=lambda x: x.get("delivery_date", ""), reverse=True)

    total = len(pos)

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": pos[start:end]
    }

@router.get("/{po_id}")
def get_po(po_id: str):
    pos = read_json("purchase_orders.json")

    po = next((p for p in pos if p["id"] == po_id), None)

    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    return po

@router.post("")
def create_po(po: dict):
    pos = read_json("purchase_orders.json")

    pos.append(po)

    write_json("purchase_orders.json", pos)

    return po

@router.put("/{po_id}")
def update_po(po_id: str, updated_po: dict):
    pos = read_json("purchase_orders.json")

    for index, po in enumerate(pos):
        if po["id"] == po_id:
            pos[index] = updated_po
            write_json("purchase_orders.json", pos)
            return updated_po

    raise HTTPException(status_code=404, detail="PO not found")