from fastapi import APIRouter, Query, HTTPException
from app.utils.json_db import read_json, write_json
from datetime import datetime

router = APIRouter(prefix="/po", tags=["Purchase Orders"])


@router.get("")
def get_pos(
    page: int = 1,
    page_size: int = 50,
    status: str = None,
    supplier_id: str = None,
    procurement_specialist_id: str = None,
    sort_by: str = None,
    search: str = None,
    po_number: str = None,
    supplier_name: str = None,
    total_value_from: float = None,
    total_value_to: float = None,
    delivery_date_from: str = None,
    delivery_date_to: str = None,
    source_system: str = None,
    items_from: int = None,
    items_to: int = None,
    mrp_exceptions: str = None,
):
    pos = read_json("purchase_orders.json")
    print(f"Status filtering: {status}")
    print(f"source_system: {source_system}")
    if status:
        pos = [p for p in pos if p["status"] == status]
        print(f"Filtered by status: {len(pos)} POs found")

    if supplier_id:
        pos = [p for p in pos if p["supplier_id"] == supplier_id]

    if procurement_specialist_id:
        pos = [
            p
            for p in pos
            if p["procurement_specialist_id"] == procurement_specialist_id
        ]

    if po_number:
        po_number_lower = po_number.lower()

        pos = [
            p for p in pos
            if po_number_lower in p["po_number"].lower()
        ]

    if supplier_name:
        supplier_name_lower = supplier_name.lower()

        pos = [
            p for p in pos
            if supplier_name_lower in p["supplier_name"].lower()
        ]

    if total_value_from is not None:
        pos = [
            p for p in pos
            if p["total_value"] >= total_value_from
        ]

    if total_value_to is not None:
        pos = [
            p for p in pos
            if p["total_value"] <= total_value_to
        ]

    if source_system:
        pos = [p for p in pos if p["source_system"] == source_system]

    if items_from is not None:
        pos = [
            p for p in pos
            if len(p["line_items"]) >= items_from
        ]

    if items_to is not None:
        pos = [
            p for p in pos
            if len(p["line_items"]) <= items_to
        ]

    if mrp_exceptions:
        if mrp_exceptions == "Yes":
            pos = [p for p in pos if p["mrp_exceptions"] != "NONE"]
        elif mrp_exceptions == "No":
            pos = [p for p in pos if p["mrp_exceptions"] == "NONE"]
            
    if delivery_date_from:
        from_date = datetime.strptime(
            delivery_date_from,
            "%Y-%m-%d"
        ).date()

        pos = [
            p for p in pos
            if datetime.strptime(
                p["delivery_date"],
                "%Y-%m-%d"
            ).date() >= from_date
        ]

    if delivery_date_to:
        to_date = datetime.strptime(
            delivery_date_to,
            "%Y-%m-%d"
        ).date()

        pos = [
            p for p in pos
            if datetime.strptime(
                p["delivery_date"],
                "%Y-%m-%d"
            ).date() <= to_date
        ]

    # Search filter
    if search:
        search_lower = search.lower()
        pos = [
            p
            for p in pos
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
        "data": pos[start:end],
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
