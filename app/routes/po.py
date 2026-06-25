from copy import deepcopy
from datetime import datetime
import logging
import mimetypes
import os
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from jose import JWTError

from app.db.models import PODocument, POStatusHistory, User
from app.db.session import SessionLocal
from app.utils.auth import decode_token, extract_bearer_token
from app.utils.postgres_db import (
    create_relational_purchase_order,
    find_relational_purchase_order,
    query_relational_purchase_orders,
    replace_relational_purchase_order,
)

router = APIRouter(prefix="/po", tags=["Purchase Orders"])
logger = logging.getLogger(__name__)


PS_ACTIONS = [
    "MOVE_IN",
    "MOVE_OUT",
    "SPLIT",
    "HOLD",
    "REJECT",
    "ACCEPT",
    "ACKNOWLEDGE",
    "NEED_MORE_INFORMATION",
]

SUPPLIER_ACTIONS = [
    "MAKE_REVISION",
    "PROPOSE_CHANGE",
    "RAISE_CONCESSION",
    "UPLOAD_DOCUMENT",
    "SPLIT",
    "HOLD",
    "ACKNOWLEDGE",
    "ACCEPT",
]

ACTION_STATUS_TRANSITIONS = {
    "MOVE_IN": "IN_PROGRESS",
    "MOVE_OUT": "IN_PROGRESS",
    "SPLIT": "IN_PROGRESS",
    "HOLD": "IN_PROGRESS",
    "REJECT": "CANCELLED",
    "ACCEPT": "APPROVED",
    "ACKNOWLEDGE": "ACKNOWLEDGED",
    "NEED_MORE_INFORMATION": "IN_PROGRESS",
    "MAKE_REVISION": "IN_PROGRESS",
    "PROPOSE_CHANGE": "IN_PROGRESS",
    "RAISE_CONCESSION": "IN_PROGRESS",
    "UPLOAD_DOCUMENT": "IN_PROGRESS",
}

DOCUMENT_ACTION_STATUS = {
    "ACCEPT": "APPROVED",
    "REJECT": "REJECTED",
    "NEED_MORE_INFORMATION": "NEEDS_MORE_INFO",
    "HOLD": "HOLD",
    "ACKNOWLEDGE": "ACKNOWLEDGED",
}

ROLE_ALLOWED_ACTIONS = {
    "PROCUREMENT_SPECIALIST": set(PS_ACTIONS),
    "SUPPLIER": set(SUPPLIER_ACTIONS),
    "ADMIN": set(PS_ACTIONS + SUPPLIER_ACTIONS),
}

UPLOAD_STORAGE_PATH = Path(os.getenv("UPLOAD_STORAGE_PATH", "data/uploads")).resolve()


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

    session = SessionLocal()
    try:
        user = session.get(User, user_id)
    finally:
        session.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "supplier_msid": user.supplier_msid,
    }


def _can_access_po(po: Dict, current_user: Dict) -> bool:
    role = current_user.get("role")
    user_id = current_user.get("id")

    if role == "ADMIN":
        return True

    if role == "SUPPLIER":
        user_supplier_msid = current_user.get("supplier_msid")
        po_supplier_msid = po.get("supplier_msid")
        if user_supplier_msid is None or po_supplier_msid is None:
            return False
        return str(user_supplier_msid) == str(po_supplier_msid)

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
        "po_line_no": line_item.get("po_line_no") or line_number,
        "po_release_no": line_item.get("po_release_no"),
        "po_line_revision_no": line_item.get("po_line_revision_no"),
        "po_line_issue_date": line_item.get("po_line_issue_date"),
        "material_code": line_item.get("material_code") or line_item.get("materialNo") or "",
        "description": line_item.get("description", ""),
        "quantity": quantity,
        "quantity_outstanding": line_item.get("quantity_outstanding"),
        "unit_price": unit_price,
        "currency_code": line_item.get("currency_code"),
        "unit": line_item.get("unit", "EA"),
        "per": line_item.get("per", 1),
        "supplier_mat_code": line_item.get("supplier_mat_code") or line_item.get("supplierMatCode", ""),
        "transportation": line_item.get("transportation", "PARCEL-GROUND B"),
        "shipment_date": line_item.get("shipment_date", ""),
        "original_promise_date": line_item.get("original_promise_date"),
        "latest_promise_date": line_item.get("latest_promise_date"),
        "required_in_house_date": line_item.get("required_in_house_date", ""),
        "net_value": line_item.get("net_value", round(quantity * unit_price, 2)),
        "item_category_id": line_item.get("item_category_id"),
        "incoterm": line_item.get("incoterm"),
        "incoterm_named_place": line_item.get("incoterm_named_place"),
        "payment_term": line_item.get("payment_term"),
        "purchasing_group": line_item.get("purchasing_group"),
        "shipment_mode": line_item.get("shipment_mode"),
        "po_line_ack_status": line_item.get("po_line_ack_status"),
        "po_line_ack_date": line_item.get("po_line_ack_date"),
        "savings_type": line_item.get("savings_type"),
        "savings": line_item.get("savings"),
        "std_unit_cost": line_item.get("std_unit_cost"),
        "erp_extract_date": line_item.get("erp_extract_date"),
        "except_message": line_item.get("except_message"),
        "rescheduling_date": line_item.get("rescheduling_date"),
        "po_feedback": line_item.get("po_feedback"),
        "drawing_no": line_item.get("drawing_no"),
        "drawing_revision": line_item.get("drawing_revision"),
        "seals_ord_no": line_item.get("seals_ord_no"),
        "updated_quantity": line_item.get("updated_quantity"),
        "updated_unit_price": line_item.get("updated_unit_price"),
        "updated_delivery_date": line_item.get("updated_delivery_date"),
        "updated_material_no": line_item.get("updated_material_no"),
        "updated_description": line_item.get("updated_description"),
        "updated_net_value": line_item.get("updated_net_value"),
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


def _load_pos() -> List[Dict]:
    pos = query_relational_purchase_orders()
    return [_normalize_po(po) for po in pos]


def _load_po(po_id: str) -> Optional[Dict]:
    po = find_relational_purchase_order(po_id)
    return _normalize_po(po) if po else None


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
    document_id: Optional[str] = None,
    move_in_date: Optional[str] = None,
    move_out_date: Optional[str] = None,
    split_rows: Optional[List[Dict]] = None,
    proposed_quantity: Optional[float] = None,
    proposed_unit_price: Optional[float] = None,
    proposed_delivery_date: Optional[str] = None,
    concession_reason: Optional[str] = None,
    concession_description: Optional[str] = None,
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
    normalized_proposed_delivery_date = (
        _validate_iso_date(proposed_delivery_date, "proposed_delivery_date")
        if proposed_delivery_date
        else None
    )

    if action == "MOVE_IN":
        if not normalized_move_in_date:
            raise HTTPException(status_code=400, detail="move_in_date is required for MOVE_IN")
        line_item["required_in_house_date"] = normalized_move_in_date

    if action == "MOVE_OUT":
        if not normalized_move_out_date:
            raise HTTPException(status_code=400, detail="move_out_date is required for MOVE_OUT")
        line_item["shipment_date"] = normalized_move_out_date

    if action == "SPLIT":
        if not split_rows:
            raise HTTPException(status_code=400, detail="splits is required for SPLIT action")
        line_item["split_deliveries"] = split_rows

    if action == "PROPOSE_CHANGE":
        if proposed_quantity is not None:
            line_item["updated_quantity"] = proposed_quantity
        if proposed_unit_price is not None:
            line_item["updated_unit_price"] = proposed_unit_price
        if normalized_proposed_delivery_date is not None:
            line_item["updated_delivery_date"] = normalized_proposed_delivery_date

        quantity_for_total = (
            float(proposed_quantity)
            if proposed_quantity is not None
            else float(line_item.get("quantity") or 0)
        )
        unit_price_for_total = (
            float(proposed_unit_price)
            if proposed_unit_price is not None
            else float(line_item.get("unit_price") or 0)
        )
        line_item["updated_net_value"] = round(quantity_for_total * unit_price_for_total, 2)

    if action == "RAISE_CONCESSION":
        line_item["concession"] = concession_reason or ""
        if concession_description:
            line_item["concession_description"] = concession_description

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
    if action == "SPLIT":
        history_record["split_rows"] = split_rows
    if action == "PROPOSE_CHANGE":
        history_record["proposed_quantity"] = proposed_quantity
        history_record["proposed_unit_price"] = proposed_unit_price
        history_record["proposed_delivery_date"] = normalized_proposed_delivery_date
        history_record["proposed_net_value"] = line_item.get("updated_net_value")
    if action == "RAISE_CONCESSION":
        history_record["concession_reason"] = concession_reason or ""
        history_record["concession_description"] = concession_description or ""
    if document_id:
        history_record["document_id"] = document_id

    updated_po["status"] = next_status
    updated_po["last_modified_by"] = current_user.get("id")
    updated_po["last_modified_date"] = timestamp
    updated_po.setdefault("status_history", []).append(history_record)

    line_item["line_status"] = action.replace("_", " ")
    line_item.setdefault("history", []).append(history_record)

    return updated_po


def _serialize_document_row(document: PODocument) -> Dict:
    return {
        "id": document.id,
        "po_id": document.po_id,
        "line_item_id": document.line_item_id,
        "file_name": document.file_name,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "file_path": document.file_path,
        "status": document.status,
        "document_tag_to": document.document_tag_to,
        "version": document.version,
        "ps_comments": document.ps_comments,
        "uploaded_by": document.uploaded_by,
        "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


def _serialize_history_row(history: POStatusHistory) -> Dict:
    return {
        "id": history.id,
        "po_id": history.po_id,
        "line_item_id": history.line_item_id,
        "action": history.action,
        "actor_id": history.actor_id,
        "actor_role": history.actor_role,
        "previous_status": history.previous_status,
        "new_status": history.new_status,
        "notes": history.notes,
        "move_in_date": history.move_in_date.isoformat() if history.move_in_date else None,
        "move_out_date": history.move_out_date.isoformat() if history.move_out_date else None,
        "created_at": history.created_at.isoformat() if history.created_at else None,
    }


def _insert_history_row(po_id: str, history_record: Dict) -> None:
    session = SessionLocal()
    try:
        row = POStatusHistory(
            po_id=po_id,
            line_item_id=history_record.get("line_item_id"),
            action=history_record.get("action") or "",
            actor_id=history_record.get("actor_id") or "",
            actor_role=history_record.get("actor_role") or "",
            previous_status=history_record.get("previous_status"),
            new_status=history_record.get("new_status"),
            notes=history_record.get("notes"),
            move_in_date=datetime.strptime(history_record["move_in_date"], "%Y-%m-%d").date()
            if history_record.get("move_in_date")
            else None,
            move_out_date=datetime.strptime(history_record["move_out_date"], "%Y-%m-%d").date()
            if history_record.get("move_out_date")
            else None,
        )
        session.add(row)
        session.commit()
    finally:
        session.close()


def _list_history_for_po(po_id: str) -> List[Dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(POStatusHistory)
            .filter(POStatusHistory.po_id == po_id)
            .order_by(POStatusHistory.created_at.desc())
            .all()
        )
        return [_serialize_history_row(row) for row in rows]
    finally:
        session.close()


def _list_documents_for_po(po_id: str) -> List[Dict]:
    session = SessionLocal()
    try:
        rows = session.query(PODocument).filter(PODocument.po_id == po_id).all()
        return [_serialize_document_row(row) for row in rows]
    finally:
        session.close()


def _get_document_or_404(session, po_id: str, document_id: str):
    document = (
        session.query(PODocument)
        .filter(PODocument.id == document_id, PODocument.po_id == po_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


#fuction to include Buyer details in PO
def enrich_buyer_details(pos):
    session = SessionLocal()
    try:
        ps_rows = session.query(User).filter(User.role == "PROCUREMENT_SPECIALIST").all()
    finally:
        session.close()

    ps_map = {u.id: u for u in ps_rows}

    for po in pos:
        ps = ps_map.get(po.get("procurement_specialist_id"))

        po["buyer_name"] = ps.name if ps and ps.name else ""
        po["buyer_email"] = ps.email if ps and ps.email else ""
        po["buyer_phone"] = ps.phone if ps and ps.phone else ""

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
    pos = _load_pos()
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
        pos = [p for p in pos if p["site"] == site]

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

    #include buyer details in the PO list
    enrich_buyer_details(pos)

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

    pos = _load_pos()
    pos = [po for po in pos if _can_access_po(po, current_user)]

    session = SessionLocal()
    try:
        user = session.get(User, user_id)
    finally:
        session.close()

    pinned_po_ids = list(user.pinned_rows or []) if user else []

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

@router.get("/{po_id}")
def get_po(po_id: str, authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)
    po = _load_po(po_id)

    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    
    # supplier_map = {}
    # for s in all_suppliers:
    #     # Check every possible property where the string "SUP-006" could be stored
    #     raw_id = s.get("id") or s.get("supplier_id") or s.get("_id")
    #     if raw_id:
    #         # Clean up the key to avoid space or object ID formatting issues
    #         clean_key = str(raw_id).strip().upper()
    #         supplier_map[clean_key] = s

    # for p in pos:
    #     s_id = p.get("supplier_id")
    #     # Match the cleaning process (strip spaces, turn uppercase)
    #     lookup_key = str(s_id).strip().upper() if s_id else None
        
    #     supplier_match = supplier_map.get(lookup_key) if lookup_key else None
        
    #     if supplier_match:
    #         p["supplier_email"] = supplier_match.get("supplier_email") or supplier_match.get("email")
    #         p["site"] = supplier_match.get("site") or supplier_match.get("location")
    #     else:
    #         # Setting these to visible string labels temporarily 
    #         # will show us on the UI if it's hitting the fallback condition
    #         p["supplier_email"] = f"No link for {s_id}"
    #         p["site"] = "Missing Site Info"

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

    try:
        inserted = create_relational_purchase_order(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

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
    existing = _load_po(po_id)
    if not existing:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(existing, current_user)

    if current_user.get("role") == "SUPPLIER":
        blocked_fields = {"supplier_id", "procurement_specialist_id", "total_value", "currency"}
        if any(field in updated_po for field in blocked_fields):
            raise HTTPException(status_code=403, detail="Supplier cannot update restricted PO fields")

    merged = {**existing, **updated_po}
    merged["id"] = po_id
    merged["last_modified_by"] = current_user.get("id")
    merged["last_modified_date"] = _now_iso()

    updated = replace_relational_purchase_order(po_id, merged)
    if not updated:
        logger.error(
            "po.update persist_failed po_id=%s actor_id=%s role=%s",
            po_id,
            current_user.get("id"),
            current_user.get("role"),
        )
        raise HTTPException(status_code=404, detail="PO not found")

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
    po = _load_po(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(po, current_user)

    action = (action_payload.get("action") or "").strip().upper()
    line_item_id = action_payload.get("line_item_id")
    line_item_ids = action_payload.get("line_item_ids")
    if isinstance(line_item_ids, list):
        line_item_ids = [str(item).strip() for item in line_item_ids if str(item).strip()]
    else:
        line_item_ids = []
    notes = (action_payload.get("notes") or "").strip()
    document_id = (action_payload.get("document_id") or "").strip()
    move_in_date = (action_payload.get("move_in_date") or action_payload.get("required_in_house_date") or "").strip()
    move_out_date = (action_payload.get("move_out_date") or action_payload.get("shipment_date") or "").strip()
    split_rows = action_payload.get("splits") if isinstance(action_payload.get("splits"), list) else None
    proposed_quantity = action_payload.get("proposed_quantity")
    proposed_unit_price = action_payload.get("proposed_unit_price")
    proposed_delivery_date = (action_payload.get("proposed_delivery_date") or "").strip()
    concession_reason = (action_payload.get("concession_reason") or "").strip()
    concession_description = (action_payload.get("concession_description") or "").strip()

    try:
        parsed_proposed_quantity = (
            float(proposed_quantity) if proposed_quantity not in (None, "") else None
        )
        parsed_proposed_unit_price = (
            float(proposed_unit_price) if proposed_unit_price not in (None, "") else None
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="proposed_quantity and proposed_unit_price must be numeric",
        ) from exc

    if not action:
        raise HTTPException(status_code=400, detail="action is required")

    logger.info(
        "po.action requested po_id=%s action=%s line_item_id=%s line_item_ids=%s document_id=%s actor_id=%s role=%s move_in_date=%s move_out_date=%s",
        po_id,
        action,
        line_item_id,
        line_item_ids,
        document_id,
        current_user.get("id"),
        current_user.get("role"),
        move_in_date or "",
        move_out_date or "",
    )

    resolved_line_ids = line_item_ids or ([line_item_id] if line_item_id else [])
    if not resolved_line_ids:
        raise HTTPException(status_code=400, detail="line_item_id is required")

    updated_po = po
    for resolved_line_id in resolved_line_ids:
        updated_po = _apply_action_to_po(
            po=updated_po,
            action=action,
            current_user=current_user,
            line_item_id=resolved_line_id,
            notes=notes,
            document_id=document_id or None,
            move_in_date=move_in_date or None,
            move_out_date=move_out_date or None,
            split_rows=split_rows,
            proposed_quantity=parsed_proposed_quantity,
            proposed_unit_price=parsed_proposed_unit_price,
            proposed_delivery_date=proposed_delivery_date or None,
            concession_reason=concession_reason or None,
            concession_description=concession_description or None,
        )

    persisted = replace_relational_purchase_order(po_id, updated_po)
    if not persisted:
        logger.error(
            "po.action persist_failed po_id=%s action=%s line_item_id=%s actor_id=%s",
            po_id,
            action,
            line_item_id,
            current_user.get("id"),
        )
        raise HTTPException(status_code=404, detail="PO not found")

    logger.info(
        "po.action success po_id=%s action=%s line_item_id=%s actor_id=%s",
        po_id,
        action,
        line_item_id,
        current_user.get("id"),
    )

    latest_history = (persisted.get("status_history") or [])[-1] if persisted.get("status_history") else None
    if latest_history:
        _insert_history_row(po_id, latest_history)

    return {
        **persisted,
        "ui_config": _get_role_ui_config(current_user.get("role", "")),
        "available_actions": _allowed_actions_for_user(current_user),
    }


@router.get("/{po_id}/history")
def get_po_history(po_id: str, authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)
    po = _load_po(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(po, current_user)
    db_history = _list_history_for_po(po_id)
    if db_history:
        return {
            "po_id": po_id,
            "history": db_history,
        }

    return {
        "po_id": po_id,
        "history": po.get("status_history", []),
    }


@router.get("/{po_id}/documents")
def get_po_documents(po_id: str, authorization: Optional[str] = Header(default=None)):
    current_user = _current_user(authorization)
    po = _load_po(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(po, current_user)
    return {
        "po_id": po_id,
        "documents": _list_documents_for_po(po_id),
    }


@router.get("/{po_id}/documents/{document_id}/download")
def download_po_document(
    po_id: str,
    document_id: str,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)
    po = _load_po(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(po, current_user)

    session = SessionLocal()
    try:
        doc = (
            session.query(PODocument)
            .filter(PODocument.id == document_id, PODocument.po_id == po_id)
            .first()
        )
    finally:
        session.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Document file missing")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(
        path=str(file_path),
        media_type=media_type or "application/octet-stream",
        filename=doc.file_name or file_path.name,
    )


@router.post("/{po_id}/documents/{document_id}/actions")
def perform_po_document_action(
    po_id: str,
    document_id: str,
    action_payload: dict,
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)
    po = _load_po(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(po, current_user)

    action = (action_payload.get("action") or "").strip().upper()
    notes = (action_payload.get("notes") or "").strip()
    if action not in DOCUMENT_ACTION_STATUS:
        raise HTTPException(status_code=400, detail="Unsupported document action")

    session = SessionLocal()
    try:
        document = _get_document_or_404(session, po_id, document_id)
        document.status = DOCUMENT_ACTION_STATUS[action]
        document.ps_comments = notes or document.ps_comments
        session.add(document)
        session.commit()
        session.refresh(document)
        return {"document": _serialize_document_row(document)}
    finally:
        session.close()


@router.post("/{po_id}/documents/{document_id}/replace")
async def replace_po_document(
    po_id: str,
    document_id: str,
    file: UploadFile = File(...),
    comments: str = Form(""),
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)
    po = _load_po(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(po, current_user)

    session = SessionLocal()
    try:
        document = _get_document_or_404(session, po_id, document_id)
        UPLOAD_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        extension = Path(file.filename or document.file_name or "document").suffix
        replacement_path = UPLOAD_STORAGE_PATH / f"{document.id}{extension}"
        content = await file.read()
        replacement_path.write_bytes(content)

        document.file_name = file.filename or document.file_name
        document.file_type = extension.lstrip(".").lower() if extension else document.file_type
        document.file_size = len(content)
        document.file_path = str(replacement_path)
        document.status = "PENDING"
        document.version = (document.version or 1) + 1
        document.ps_comments = comments or document.ps_comments
        document.uploaded_by = current_user.get("id")
        session.add(document)
        session.commit()
        session.refresh(document)
        return {"document": _serialize_document_row(document)}
    finally:
        session.close()


@router.post("/{po_id}/documents/upload")
async def upload_po_document(
    po_id: str,
    line_item_id: str = Form(...),
    file: UploadFile = File(...),
    document_tag_to: str = Form("LINE_ITEM"),
    comments: str = Form(""),
    authorization: Optional[str] = Header(default=None),
):
    current_user = _current_user(authorization)
    po = _load_po(po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    _assert_po_access(po, current_user)
    line_item = _find_line_item_or_404(po, line_item_id)

    UPLOAD_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    extension = Path(file.filename or "document").suffix
    document_id = str(uuid4())
    file_name = file.filename or f"upload{extension}"
    output_path = UPLOAD_STORAGE_PATH / f"{document_id}{extension}"

    content = await file.read()
    output_path.write_bytes(content)

    session = SessionLocal()
    try:
        document = PODocument(
            id=document_id,
            po_id=po_id,
            line_item_id=str(line_item.get("id")),
            file_name=file_name,
            file_type=extension.lstrip(".").lower() if extension else None,
            file_size=len(content),
            file_path=str(output_path),
            status="PENDING",
            document_tag_to=document_tag_to,
            version=1,
            ps_comments=comments or None,
            uploaded_by=current_user.get("id"),
        )
        session.add(document)
        session.commit()
        session.refresh(document)
    finally:
        session.close()

    line_documents = line_item.setdefault("documents", [])
    line_documents.append(
        {
            "id": document_id,
            "file_name": file_name,
            "status": "PENDING",
            "file_type": extension.lstrip(".").lower() if extension else None,
            "size": len(content),
            "uploaded_by": current_user.get("id"),
            "uploaded_at": _now_iso(),
            "comments": comments,
        }
    )

    persisted_po = replace_relational_purchase_order(po_id, po)
    if not persisted_po:
        raise HTTPException(status_code=500, detail="Failed to persist PO document state")

    return {
        "message": "Document uploaded successfully",
        "document": _serialize_document_row(document),
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
