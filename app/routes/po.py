from typing import List

from fastapi import APIRouter, Query, HTTPException
from app.utils.mongo_db import find_one, query_items, insert_one, replace_one, update_one
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
    sort_order: str = "asc",
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
    pinned_po_list: List[str] = None
):
    pos = query_items("purchase_orders")
    print(f"Status filtering: {status}")
    print(f"pinned_po_list filtering: {pinned_po_list}")
    print(f"source_system: {source_system}")
    
    # filter if pinnedPos not empty
    if pinned_po_list and len(pinned_po_list) > 0:
        pos = [p for p in pos if p["id"] in pinned_po_list]
        print(f"After pinned PO filtering: {len(pos)} POs found")

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
    print(f"POs after value filtering: {source_system}, count: {len(pos)}")
    if source_system:
        pos = [p for p in pos if p["source_system"].lower() == source_system.lower()]

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
    # if sort_by == "delivery_date_asc":
    #     pos = sorted(pos, key=lambda x: x.get("delivery_date", ""))
    # elif sort_by == "delivery_date_desc":
    #     pos = sorted(pos, key=lambda x: x.get("delivery_date", ""), reverse=True)
    print(sort_order == "desc")
    if sort_by is not None:
        pos = sorted(pos, key=lambda x: x.get(sort_by, ""), reverse=sort_order == "desc")
    print(f"POs after sorting: {len(pos)}")
    print(f"Sorting by: {sort_by}, order: {sort_order}, pos count after sorting: {len(pos)}")

    total = len(pos)

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": pos[start:end],
    }

@router.get("/pinned_po_list")
def get_pinned_pos(
    page: int = 1,
    page_size: int = 10,
    user_id: str = Query(..., description="User ID to fetch pinned POs for")
):
    pos = query_items("purchase_orders")
    pinned_po_ids = []
    users = query_items("users")
    print(f'user: {user_id}')
    for user in users:
        if user.get("id") == user_id:
            pinned_po_ids.extend(user.get("pinned_rows", []))
            break
    print(f'polist: {pinned_po_ids}')
    pos = [p for p in pos if p["id"] in pinned_po_ids]

    total = len(pos)

    start = (page - 1) * page_size
    end = start + page_size
    print('pinned: ')
    print(pos)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": pos[start:end],
    }

@router.get("/{po_id}")
def get_po(po_id: str):
    po = find_one("purchase_orders", {"id": po_id})

    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    return po


@router.post("")
def create_po(po: dict):
    inserted = insert_one("purchase_orders", po)
    return inserted


@router.put("/{po_id}")
def update_po(po_id: str, updated_po: dict):
    existing = find_one("purchase_orders", {"id": po_id})
    if not existing:
        raise HTTPException(status_code=404, detail="PO not found")

    updated = replace_one("purchase_orders", {"id": po_id}, updated_po)
    return updated
