from copy import deepcopy

from typing import List

from app.utils.mongo_db import find_one, query_items, insert_one, replace_one, update_one
from datetime import datetime
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from jose import JWTError

from app.utils.auth import decode_token, extract_bearer_token
from app.utils.mongo_db import find_one, insert_one, query_items, replace_one, update_one

router = APIRouter(prefix="/po", tags=["Purchase Orders"])
logger = logging.getLogger(__name__)


PS_ACTIONS = [
    "MOVE_IN",
    "MOVE_OUT",
    "SPLIT",
    "HOLD",
    "REJECT",
    "ACCEPT",
    "NEED_MORE_INFORMATION",
]

SUPPLIER_ACTIONS = [
    "MAKE_REVISION",
    "RAISE_CONCESSION",
    "UPLOAD_DOCUMENT",
    "ACCEPT",
]

ACTION_STATUS_TRANSITIONS = {
    "MOVE_IN": "IN_PROGRESS",
    "MOVE_OUT": "IN_PROGRESS",
    "SPLIT": "IN_PROGRESS",
    "HOLD": "IN_PROGRESS",
    "REJECT": "CANCELLED",
    "ACCEPT": "APPROVED",
    "NEED_MORE_INFORMATION": "IN_PROGRESS",
    "MAKE_REVISION": "IN_PROGRESS",
    "RAISE_CONCESSION": "IN_PROGRESS",
    "UPLOAD_DOCUMENT": "IN_PROGRESS",
}

ROLE_ALLOWED_ACTIONS = {
    "PROCUREMENT_SPECIALIST": set(PS_ACTIONS),
    "SUPPLIER": set(SUPPLIER_ACTIONS),
    "ADMIN": set(PS_ACTIONS + SUPPLIER_ACTIONS),
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _validate_iso_date(value: str, field_name: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be in YYYY-MM-DD format") from exc


def _current_user(authorization: Optional[str]) -> Dict:
    try:
        token = extract_bearer_token(authorization)
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user_id = payload.get("sub")
    role = payload.get("role")

    if not user_id or not role:
        raise HTTPException(status_code=401, detail="Token missing required fields")

    user = find_one("users", {"id": user_id})
    if not user:
        user = find_one("suppliers", {"id": user_id})

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role"),
    }


def _can_access_po(po: Dict, current_user: Dict) -> bool:
    role = current_user.get("role")
    user_id = current_user.get("id")

    if role == "ADMIN":
        return True

    if role == "SUPPLIER":
        return po.get("supplier_id") == user_id

    if role == "PROCUREMENT_SPECIALIST":
        return user_id in {
            po.get("procurement_specialist_id"),
            po.get("delegated_user_id"),
        }

    return False


def _assert_po_access(po: Dict, current_user: Dict) -> None:
    if not _can_access_po(po, current_user):
        raise HTTPException(status_code=403, detail="Forbidden to access this PO")


def _default_billing_details(po: Dict) -> Dict:
    return {
        "terms_of_payment": po.get("payment_terms", ""),
        "currency": po.get("currency", ""),
        "send_invoice_to": "",
        "bill_to_address": "",
    }


def _default_po_details(po: Dict) -> Dict:
    return {
        "supplier_details": {
            "supplier_no": po.get("supplier_id", ""),
            "email": "",
            "address": "",
        },
        "buyer_details": {
            "buyer": po.get("procurement_specialist_id", ""),
            "telephone": "",
            "email": "",
        },
        "shipment_details": {
            "incoterms": "",
            "address": "",
        },
        "billing_details": _default_billing_details(po),
    }


def _normalize_line_item(line_item: Dict, index: int) -> Dict:
    line_number = line_item.get("line_number", index + 1)
    line_id = line_item.get("id") or str(line_number).zfill(5)
    quantity = line_item.get("quantity", 0)
    unit_price = line_item.get("unit_price", 0)

    return {
        "id": line_id,
        "line_number": line_number,
        "material_code": line_item.get("material_code") or line_item.get("materialNo") or "",
        "description": line_item.get("description", ""),
        "quantity": quantity,
        "unit_price": unit_price,
        "unit": line_item.get("unit", "EA"),
        "per": line_item.get("per", 1),
        "supplier_mat_code": line_item.get("supplier_mat_code") or line_item.get("supplierMatCode", ""),
        "transportation": line_item.get("transportation", "PARCEL-GROUND B"),
        "shipment_date": line_item.get("shipment_date", ""),
        "required_in_house_date": line_item.get("required_in_house_date", ""),
        "net_value": line_item.get("net_value", round(quantity * unit_price, 2)),
        "updated_quantity": line_item.get("updated_quantity"),
        "updated_unit_price": line_item.get("updated_unit_price"),
        "updated_delivery_date": line_item.get("updated_delivery_date"),
        "updated_material_no": line_item.get("updated_material_no"),
        "updated_description": line_item.get("updated_description"),
        "updated_net_value": line_item.get("updated_net_value"),

        # New PO Review / MRP Exception fields
        "supplier_confirmation_date": line_item.get("supplier_confirmation_date", ""),
        "recommendation": line_item.get("recommendation", ""),
        "exception_type": line_item.get("exception_type", ""),
        "mrp_action_required": line_item.get("mrp_action_required", False),
        "concession": line_item.get("concession", ""),

        "documents": line_item.get("documents", []),
        "line_status": line_item.get("line_status", "ALL"),
        "default_expanded": line_item.get("default_expanded", index < 3),
        "history": line_item.get("history", []),
    }


def _normalize_po(po: Dict) -> Dict:
    normalized = deepcopy(po)
    normalized["po_details"] = normalized.get("po_details") or _default_po_details(normalized)

    line_items = normalized.get("line_items", [])
    normalized["line_items"] = [
        _normalize_line_item(line_item, index) for index, line_item in enumerate(line_items)
    ]

    normalized["status_history"] = normalized.get("status_history", [])
    normalized["workflow_stage"] = normalized.get("workflow_stage", "PO_DETAILS")
    normalized["last_modified_by"] = normalized.get("last_modified_by", "")
    normalized["last_modified_date"] = normalized.get("last_modified_date", "")

    return normalized


def _get_role_ui_config(role: str) -> Dict:
    if role == "SUPPLIER":
        return {
            "main_tabs": [
                "PO DETAILS",
                "DOCUMENTS REPOSITORY",
                "REVISION",
                "SHIPMENT & TRACKING",
            ],
            "header_actions": ["EXPORT"],
            "line_status_tabs": [
                "ALL",
                "ACCEPTED",
                "REVISED",
                "CONCESSION",
                "SPLIT PO",
                "REJECTED",
                "HOLD",
                "IN_PROGRESS",
                "APPROVED",
                "CANCELLED",
                "DELIVERED",
            ],
            "line_actions": SUPPLIER_ACTIONS,
            "layout": {
                "show_mrp_tab": False,
                "show_supplier_total_row": True,
                "show_bottom_page_action_bar": True,
                "show_ps_bottom_summary": False,
            },
        }

    return {
        "main_tabs": [
            "PO DETAILS",
            "MRP EXCEPTIONS",
            "DOCUMENTS REPOSITORY",
            "REVISION",
            "SHIPMENT & TRACKING",
        ],
        "header_actions": ["ASN", "PACKAGING", "EXPORT", "GRID", "CARD"],
        "line_status_tabs": [
            "ALL",
            "REVISED",
            "CONCESSION",
            "SPLIT PO",
            "REJECTED",
            "ACCEPTED",
            "NEED MORE INFO",
                "HOLD",
                "IN_PROGRESS",
                "APPROVED",
                "CANCELLED",
                "DELIVERED",
        ],
        "line_actions": PS_ACTIONS,
        "layout": {
            "show_mrp_tab": True,
            "show_supplier_total_row": False,
            "show_bottom_page_action_bar": False,
            "show_ps_bottom_summary": True,
        },
    }


def _allowed_actions_for_user(current_user: Dict) -> List[str]:
    role = current_user.get("role")
    return sorted(ROLE_ALLOWED_ACTIONS.get(role, set()))


def _find_line_item_or_404(po: Dict, line_item_id: Optional[str]) -> Dict:
    if not line_item_id:
        raise HTTPException(status_code=400, detail="line_item_id is required")

    for line_item in po.get("line_items", []):
        normalized_id = str(line_item.get("id", ""))
        line_number = str(line_item.get("line_number", "")).zfill(5)
        if line_item_id in {normalized_id, line_number}:
            return line_item

    raise HTTPException(status_code=404, detail="Line item not found")


def _apply_action_to_po(
    po: Dict,
    action: str,
    current_user: Dict,
    line_item_id: Optional[str],
    notes: str,
    move_in_date: Optional[str] = None,
    move_out_date: Optional[str] = None,
) -> Dict:
    role = current_user.get("role")
    allowed = ROLE_ALLOWED_ACTIONS.get(role, set())

    if action not in allowed:
        raise HTTPException(status_code=403, detail="Action not allowed for current role")

    next_status = ACTION_STATUS_TRANSITIONS.get(action)
    if not next_status:
        raise HTTPException(status_code=400, detail="Unsupported action")

    updated_po = _normalize_po(po)
    old_status = updated_po.get("status")
    line_item = _find_line_item_or_404(updated_po, line_item_id)
    timestamp = _now_iso()
    normalized_move_in_date = _validate_iso_date(move_in_date, "move_in_date") if move_in_date else None
    normalized_move_out_date = _validate_iso_date(move_out_date, "move_out_date") if move_out_date else None

    if action == "MOVE_IN":
        if not normalized_move_in_date:
            raise HTTPException(status_code=400, detail="move_in_date is required for MOVE_IN")
        line_item["required_in_house_date"] = normalized_move_in_date

    if action == "MOVE_OUT":
        if not normalized_move_out_date:
            raise HTTPException(status_code=400, detail="move_out_date is required for MOVE_OUT")
        line_item["shipment_date"] = normalized_move_out_date

    history_record = {
        "action": action,
        "actor_id": current_user.get("id"),
        "actor_role": role,
        "line_item_id": line_item.get("id"),
        "previous_status": old_status,
        "new_status": next_status,
        "notes": notes or "",
        "timestamp": timestamp,
    }
    if normalized_move_in_date:
        history_record["move_in_date"] = normalized_move_in_date
    if normalized_move_out_date:
        history_record["move_out_date"] = normalized_move_out_date

    updated_po["status"] = next_status
    updated_po["last_modified_by"] = current_user.get("id")
    updated_po["last_modified_date"] = timestamp
    updated_po.setdefault("status_history", []).append(history_record)

    line_item["line_status"] = action.replace("_", " ")
    line_item.setdefault("history", []).append(history_record)

    return updated_po

#fuction to include Buyer details in PO
def enrich_buyer_details(pos):
    users = query_items("users")

    ps_map = {
        u["id"]: u
        for u in users
        if u.get("role") == "PROCUREMENT_SPECIALIST"
    }

    for po in pos:
        ps = ps_map.get(po.get("procurement_specialist_id"))

        po["buyer_name"] = ps.get("name", "") if ps else ""
        po["buyer_email"] = ps.get("email", "") if ps else ""
        po["buyer_phone"] = ps.get("phone", "") if ps else ""

def _parse_csv_filter(value: Optional[str]) -> List[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]

@router.get("")
def get_pos(
    page: int = 1,
    page_size: int = 50,
    status: str = None,
    supplier_id: str = None,
    supplier_email: str = None,
    site: str = None,
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
    pinned_po_list: List[str] = None,
    authorization: Optional[str] = Header(default=None),
    revision_changes: int = None,
):
    current_user = _current_user(authorization)
    pos = query_items("purchase_orders")
    pos = [_normalize_po(po) for po in pos]
    pos = [po for po in pos if _can_access_po(po, current_user)]
    
    # filter if pinnedPos not empty
    if pinned_po_list and len(pinned_po_list) > 0:
        pos = [p for p in pos if p["id"] in pinned_po_list]
    if status:
        pos = [p for p in pos if p["status"] == status]

    if supplier_id:
        pos = [p for p in pos if p["supplier_id"] == supplier_id]

    if supplier_email:
        pos = [p for p in pos if p["supplier_email"] == supplier_email]

    if site:
        selected_sites = _parse_csv_filter(site)

        if selected_sites:
            pos = [
                p
                for p in pos
                if p.get("site") in selected_sites
            ]

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
        pos = [p for p in pos if p["source_system"].lower() == source_system.lower()]

    if revision_changes is not None:
        pos = [p for p in pos if p.get("revision_changes") == revision_changes]
    
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

    #include buyer details in the PO list
    enrich_buyer_details(pos)

    # Search filter
    if search:
        search_lower = search.lower().strip()

        pos = [
            p
            for p in pos
            if (
                search_lower in p.get("po_number", "").lower()
                or search_lower in p.get("supplier_name", "").lower()
                or search_lower in p.get("supplier_email", "").lower()
                or search_lower in p.get("supplier_id", "").lower()
                or search_lower in p.get("site", "").lower()
                or search_lower in p.get("status", "").lower()
                or search_lower in p.get("source_system", "").lower()
                or search_lower in p.get("buyer_name", "").lower()
                or search_lower in p.get("buyer_email", "").lower()
                or any(
                    search_lower in item.get("material_code", "").lower()
                    or search_lower in item.get("description", "").lower()
                    for item in p.get("line_items", [])
                )
            )
        ]

    # Sorting
    # if sort_by == "delivery_date_asc":
    #     pos = sorted(pos, key=lambda x: x.get("delivery_date", ""))
    # elif sort_by == "delivery_date_desc":
    #     pos = sorted(pos, key=lambda x: x.get("delivery_date", ""), reverse=True)

    if sort_by is not None:
        pos = sorted(pos, key=lambda x: x.get(sort_by, ""), reverse=sort_order == "desc")

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
    user_id: str = Query(..., description="User ID to fetch pinned POs for"),
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)
    if current_user.get("role") != "ADMIN" and current_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden to access pinned PO list")

    pos = query_items("purchase_orders")
    pos = [_normalize_po(po) for po in pos]
    pos = [po for po in pos if _can_access_po(po, current_user)]
    pinned_po_ids = []

    for table in ["users", "suppliers"]:
        for record in query_items(table):
            if record.get("id") == user_id:
                pinned_po_ids.extend(record.get("pinned_rows", []))
                break

        if pinned_po_ids:
            break

    pos = [p for p in pos if p["id"] in pinned_po_ids]
    enrich_buyer_details(pos)
    total = len(pos)

    start = (page - 1) * page_size
    end = start + page_size
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": pos[start:end],
    }

@router.get("/config/sites")
def get_available_sites(authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)

    pos = query_items("purchase_orders")
    pos = [_normalize_po(po) for po in pos]
    pos = [po for po in pos if _can_access_po(po, current_user)]

    sites = sorted(
        {
            po.get("site")
            for po in pos
            if po.get("site")
        }
    )

    return {
        "sites": sites
    }

@router.get("/{po_id}")
def get_po(po_id: str, authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)
    po = find_one("purchase_orders", {"id": po_id})

    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    normalized_po = _normalize_po(po)
    _assert_po_access(normalized_po, current_user)

    return {
        **normalized_po,
        "ui_config": _get_role_ui_config(current_user.get("role", "")),
        "available_actions": _allowed_actions_for_user(current_user),
    }


@router.post("")
def create_po(po: dict, authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)
    if current_user.get("role") not in {"ADMIN", "PROCUREMENT_SPECIALIST"}:
        raise HTTPException(status_code=403, detail="Forbidden to create PO")

    payload = _normalize_po(po)
    payload["last_modified_by"] = current_user.get("id")
    payload["last_modified_date"] = _now_iso()

    inserted = insert_one("purchase_orders", payload)
    logger.info(
        "po.create success po_id=%s actor_id=%s role=%s",
        inserted.get("id"),
        current_user.get("id"),
        current_user.get("role"),
    )
    return inserted


@router.put("/{po_id}")
def update_po(po_id: str, updated_po: dict, authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)
    existing = find_one("purchase_orders", {"id": po_id})
    if not existing:
        raise HTTPException(status_code=404, detail="PO not found")

    normalized_existing = _normalize_po(existing)
    _assert_po_access(normalized_existing, current_user)

    if current_user.get("role") == "SUPPLIER":
        blocked_fields = {"supplier_id", "procurement_specialist_id", "total_value", "currency"}
        if any(field in updated_po for field in blocked_fields):
            raise HTTPException(status_code=403, detail="Supplier cannot update restricted PO fields")

    merged = {**normalized_existing, **updated_po}
    merged["id"] = po_id
    merged["last_modified_by"] = current_user.get("id")
    merged["last_modified_date"] = _now_iso()

    updated = replace_one("purchase_orders", {"id": po_id}, merged)
    if not updated:
        logger.error(
            "po.update persist_failed po_id=%s actor_id=%s role=%s",
            po_id,
            current_user.get("id"),
            current_user.get("role"),
        )
        raise HTTPException(status_code=500, detail="Failed to persist PO update")

    logger.info(
        "po.update success po_id=%s actor_id=%s role=%s",
        po_id,
        current_user.get("id"),
        current_user.get("role"),
    )
    return updated


@router.post("/{po_id}/actions")
def perform_po_action(
    po_id: str,
    action_payload: dict,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)
    po = find_one("purchase_orders", {"id": po_id})
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    normalized_po = _normalize_po(po)
    _assert_po_access(normalized_po, current_user)

    action = (action_payload.get("action") or "").strip().upper()
    line_item_id = action_payload.get("line_item_id")
    notes = (action_payload.get("notes") or "").strip()
    move_in_date = (action_payload.get("move_in_date") or action_payload.get("required_in_house_date") or "").strip()
    move_out_date = (action_payload.get("move_out_date") or action_payload.get("shipment_date") or "").strip()

    if not action:
        raise HTTPException(status_code=400, detail="action is required")

    logger.info(
        "po.action requested po_id=%s action=%s line_item_id=%s actor_id=%s role=%s move_in_date=%s move_out_date=%s",
        po_id,
        action,
        line_item_id,
        current_user.get("id"),
        current_user.get("role"),
        move_in_date or "",
        move_out_date or "",
    )

    updated_po = _apply_action_to_po(
        po=normalized_po,
        action=action,
        current_user=current_user,
        line_item_id=line_item_id,
        notes=notes,
        move_in_date=move_in_date or None,
        move_out_date=move_out_date or None,
    )

    persisted = replace_one("purchase_orders", {"id": po_id}, updated_po)
    if not persisted:
        logger.error(
            "po.action persist_failed po_id=%s action=%s line_item_id=%s actor_id=%s",
            po_id,
            action,
            line_item_id,
            current_user.get("id"),
        )
        raise HTTPException(status_code=500, detail="Failed to persist PO action")

    logger.info(
        "po.action success po_id=%s action=%s line_item_id=%s actor_id=%s",
        po_id,
        action,
        line_item_id,
        current_user.get("id"),
    )

    return {
        **persisted,
        "ui_config": _get_role_ui_config(current_user.get("role", "")),
        "available_actions": _allowed_actions_for_user(current_user),
    }


@router.get("/config/dropdowns")
def get_po_dropdown_config(authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)
    role = current_user.get("role", "")

    return {
        "role": role,
        "ui_config": _get_role_ui_config(role),
        "actions": _allowed_actions_for_user(current_user),
        "status_transitions": ACTION_STATUS_TRANSITIONS,
    }
