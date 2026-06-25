import json
import hashlib
import logging
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.models import (
    ChatMessage,
    ChatSession,
    ChatUserMap,
    Delegation,
    ItemMaster,
    LocationMaster,
    PurchaseOrderLine,
    SupplierMaster,
    User,
    ACSChatCollection,
    ChatMessageCollection,
    ChatSessionCollection,
    ChatUserMapCollection,
    DelegationCollection,
    PurchaseOrderCollection,
    SupplierCollection,
    UserCollection,
)
from app.db.session import Base, DATABASE_URL, SessionLocal, engine

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
CANONICAL_DIR = DATA_DIR / "canonical"

logger = logging.getLogger(__name__)

NULL_STRINGS = {"NULL", "NONE", "N/A", "NA", "NAN"}
CollectionModel = Type[
    UserCollection
    | SupplierCollection
    | PurchaseOrderCollection
    | DelegationCollection
    | ChatSessionCollection
    | ACSChatCollection
    | ChatMessageCollection
    | ChatUserMapCollection
]

COLLECTION_MODELS: Dict[str, CollectionModel] = {
    "users": UserCollection,
    "suppliers": SupplierCollection,
    "purchase_orders": PurchaseOrderCollection,
    "delegations": DelegationCollection,
    "chat_sessions": ChatSessionCollection,
    "acs_chat_collection": ACSChatCollection,
    "chat_messages": ChatMessageCollection,
    "chat_user_map": ChatUserMapCollection,
}


@contextmanager
def _session_scope() -> Iterable[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text.upper() in NULL_STRINGS:
        return None
    return text if text else None


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value).strip()))
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def _safe_bool(value: Any, default: Optional[bool] = None) -> Optional[bool]:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "t"}:
        return True
    if normalized in {"0", "false", "no", "n", "f"}:
        return False
    return default
def _matches_filter(document: Dict[str, Any], filter_value: Dict[str, Any]) -> bool:
    for key, expected in filter_value.items():
        actual = document.get(key)

        if isinstance(expected, dict):
            if "$all" in expected:
                required_values = expected.get("$all") or []
                if not isinstance(actual, list):
                    return False
                if not all(item in actual for item in required_values):
                    return False
                continue

        if actual != expected:
            return False
    return True


def _safe_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.upper() in NULL_STRINGS:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _safe_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def _to_location_id(value: Any, fallback: int) -> int:
    parsed = _safe_int(value)
    if parsed is not None:
        return parsed
    text = _safe_str(value)
    if not text:
        return fallback
    digits = "".join(ch for ch in text if ch.isdigit())
    parsed = _safe_int(digits)
    return parsed if parsed is not None else fallback


def _to_supplier_msid(value: Any, fallback: int) -> int:
    parsed = _safe_int(value)
    if parsed is not None:
        return parsed
    text = _safe_str(value)
    if not text:
        return fallback
    if "-" in text:
        parsed = _safe_int(text.split("-")[-1])
        if parsed is not None:
            return parsed
    digits = "".join(ch for ch in text if ch.isdigit())
    parsed = _safe_int(digits)
    return parsed if parsed is not None else fallback


def _load_json_records(file_name: str) -> List[Dict[str, Any]]:
    path = DATA_DIR / file_name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as input_file:
        payload = json.load(input_file)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    return []


def _ensure_database_exists() -> None:
    if "postgresql" not in DATABASE_URL:
        return

    try:
        db_name = DATABASE_URL.rsplit("/", 1)[-1]
        server_url = DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
        server_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
        with server_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name})
            if not result.fetchone():
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("Created PostgreSQL database '%s'", db_name)
        server_engine.dispose()
    except Exception as exc:
        logger.warning("Could not ensure database exists: %s", exc)


def regenerate_purchase_orders_json_from_xlsx() -> None:
    enabled = os.getenv("SEED_REGENERATE_FROM_XLSX", "false").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return

    excel_file = Path(os.getenv("OPEN_PO_EXCEL_PATH", str(BASE_DIR / "scripts" / "Open PO Data for Xoriant (1).xlsx")))
    script_path = BASE_DIR / "scripts" / "seed_purchase_orders_from_excel.py"
    if not excel_file.exists() or not script_path.exists():
        raise RuntimeError("XLSX source or seed script missing")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            str(excel_file),
            "--output",
            str(DATA_DIR / "purchase_orders.json"),
            "--write-derived-masters",
        ],
        check=True,
    )


def _seed_suppliers(session: Session, supplier_rows: List[Dict[str, Any]]) -> None:
    for idx, row in enumerate(supplier_rows, start=1):
        msid = _to_supplier_msid(_coalesce(row.get("msid"), row.get("local_supplier_id"), row.get("id")), idx)
        existing = session.get(SupplierMaster, msid)
        supplier = existing or SupplierMaster(msid=msid, supplier_name=_safe_str(row.get("supplier_name") or row.get("name")) or f"Supplier {msid}")

        supplier.supplier_name = _safe_str(row.get("supplier_name") or row.get("name")) or supplier.supplier_name
        supplier.supplier_dba_name = _safe_str(row.get("supplier_dba_name"))
        supplier.category_id = _safe_int(row.get("category_id"))
        supplier.category_id2 = _safe_int(row.get("category_id2"))
        supplier.slp_id = _safe_str(row.get("slp_id"))
        supplier.address = _safe_str(row.get("address"))
        supplier.city = _safe_str(row.get("city"))
        supplier.state_province = _safe_str(row.get("state_province"))
        supplier.iso_country_code = _safe_str(row.get("iso_country_code"))
        supplier.postal_code = _safe_str(row.get("postal_code"))
        supplier.payment_term = _safe_str(row.get("payment_term"))
        supplier.incoterm = _safe_str(row.get("incoterm"))
        supplier.segmentation = _safe_str(row.get("segmentation"))
        supplier.tactical_approach = _safe_str(row.get("tactical_approach") or row.get("tatical_approach"))
        supplier.approval_status = _safe_str(row.get("approval_status"))
        supplier.scobc_ack = _safe_str(row.get("scobc_ack"))
        supplier.slp_nda_ack = _safe_str(row.get("slp_nda_ack"))
        supplier.scobc_received = _safe_str(row.get("scobc_received"))
        supplier.scobc_understood = _safe_str(row.get("scobc_understood"))
        supplier.company_size = _safe_int(row.get("company_size"))
        supplier.scobc_accept = _safe_str(row.get("scobc_accept"))
        supplier.is_parent = _safe_bool(row.get("is_parent"))
        supplier.duns_no = _safe_str(row.get("duns_no"))
        supplier.bp_type = _safe_str(row.get("bp_type"))
        supplier.mdg_managed = _safe_bool(row.get("mdg_managed"))
        supplier.bp_block = _safe_bool(row.get("bp_block"))
        supplier.posting_block = _safe_bool(row.get("posting_block"))
        supplier.po_block = _safe_bool(row.get("po_block"))
        supplier.diversity = _safe_str(row.get("diversity"))
        supplier.management_model = _safe_str(row.get("management_model"))
        supplier.assigned_sqe = _safe_str(row.get("assigned_sqe"))
        supplier.supplier_manager = _safe_str(row.get("supplier_manager"))
        supplier.due_diligence = _safe_str(row.get("due_diligence"))
        supplier.is_archived = _safe_bool(row.get("is_archived"), default=False)
        supplier.supplier_business_focus = _safe_str(row.get("supplier_business_focus"))

        session.add(supplier)


def _seed_locations(session: Session, location_rows: List[Dict[str, Any]]) -> None:
    for idx, row in enumerate(location_rows, start=1):
        location_id = _to_location_id(_coalesce(row.get("location_id"), row.get("location")), idx)
        existing = session.get(LocationMaster, location_id)
        location = existing or LocationMaster(
            location_id=location_id,
            location_name=_safe_str(row.get("location_name") or row.get("location")) or f"Site-{location_id}",
            platform=_safe_str(row.get("platform")) or "UNKNOWN",
            iso_country_code=_safe_str(row.get("iso_country_code")) or "US",
            sector=_safe_str(row.get("sector")) or "",
            division=_safe_str(row.get("division")) or "",
            location_type=_safe_str(row.get("location_type")) or "",
            heritage_name=_safe_str(row.get("heritage_name")) or "",
            operating_model=_safe_str(row.get("operating_model")) or "",
            platform_management_region=_safe_str(row.get("platform_management_region")) or "",
            is_balanced_scorecard=_safe_bool(row.get("is_balanced_scorecard"), default=False) or False,
            business_unit=_safe_str(row.get("business_unit")) or "",
            ru_no=_safe_str(row.get("ru_no")) or "",
            custom_bu=_safe_str(row.get("custom_bu")) or "",
        )

        location.location_name = _safe_str(row.get("location_name") or row.get("location")) or location.location_name
        location.platform = _safe_str(row.get("platform")) or location.platform
        location.iso_country_code = _safe_str(row.get("iso_country_code")) or location.iso_country_code
        location.address = _safe_str(row.get("address"))
        location.city = _safe_str(row.get("city"))
        location.state_province = _safe_str(row.get("state_province"))
        location.postal_code = _safe_str(row.get("postal_code"))
        location.operation = _safe_str(row.get("operation"))
        location.sector = _safe_str(row.get("sector")) or location.sector
        location.division = _safe_str(row.get("division")) or location.division
        location.istp_flag = _safe_bool(row.get("istp_flag"))
        location.location_status = _safe_bool(row.get("location_status"), default=True)
        location.location_type = _safe_str(row.get("location_type")) or location.location_type
        location.heritage_name = _safe_str(row.get("heritage_name")) or location.heritage_name
        location.operating_model = _safe_str(row.get("operating_model")) or location.operating_model
        location.platform_management_region = _safe_str(row.get("platform_management_region")) or location.platform_management_region
        location.is_balanced_scorecard = _safe_bool(row.get("is_balanced_scorecard"), default=location.is_balanced_scorecard)
        location.business_unit = _safe_str(row.get("business_unit")) or location.business_unit
        location.ru_no = _safe_str(row.get("ru_no")) or location.ru_no
        location.is_archived = _safe_bool(row.get("is_archived"), default=False)
        location.custom_bu = _safe_str(row.get("custom_bu")) or location.custom_bu

        session.add(location)


def _seed_items(session: Session, item_rows: List[Dict[str, Any]]) -> None:
    for idx, row in enumerate(item_rows, start=1):
        item_no = _safe_str(row.get("item_no") or row.get("material_code"))
        if not item_no:
            continue

        location_id = _to_location_id(_coalesce(row.get("location_id"), row.get("location")), 100000 + idx)
        if session.get(LocationMaster, location_id) is None:
            continue

        existing = session.get(ItemMaster, item_no)
        item = existing or ItemMaster(
            item_no=item_no,
            location_id=location_id,
            item_lead_time=_safe_int(row.get("item_lead_time") or row.get("item_le_time")) or 0,
            material_code=_safe_str(row.get("material_code")) or item_no,
            is_active=_safe_bool(row.get("is_active"), default=True) or True,
            is_safety_stock=_safe_bool(row.get("is_safety_stock"), default=False) or False,
        )

        item.location_id = location_id
        item.site_code = _safe_str(row.get("site_code"))
        item.item_lead_time = _safe_int(row.get("item_lead_time") or row.get("item_le_time")) or 0
        item.pattern_no = _safe_str(row.get("pattern_no"))
        item.material_code = _safe_str(row.get("material_code")) or item.material_code
        item.item_weight = _safe_float(row.get("item_weight"))
        item.item_weight_unit = _safe_str(row.get("item_weight_unit")) or "KG"
        item.is_active = _safe_bool(row.get("is_active"), default=True) or False
        item.is_safety_stock = _safe_bool(row.get("is_safety_stock"), default=False) or False
        item.safety_stock_min = _safe_int(row.get("safety_stock_min"))
        item.safety_stock_max = _safe_int(row.get("safety_stock_max"))
        item.stock_level = _safe_int(row.get("stock_level"))

        session.add(item)


def _ensure_item(session: Session, item_no: str, location_id: int) -> None:
    if session.get(ItemMaster, item_no) is not None:
        return
    session.add(
        ItemMaster(
            item_no=item_no,
            location_id=location_id,
            item_lead_time=0,
            material_code=item_no,
            is_active=True,
            is_safety_stock=False,
        )
    )

    if isinstance(row, DelegationCollection):
        row.status = payload.get("status")
        row.delegated_from_id = payload.get("delegated_from_id")
        row.delegated_to_id = payload.get("delegated_to_id")
        row.po_id = payload.get("po_id")
        return

    if isinstance(row, ChatSessionCollection):
        row.po_id = payload.get("po_id")
        row.status = payload.get("status")
        row.chat_type = payload.get("chat_type")
        return

    if isinstance(row, ACSChatCollection):
        row.thread_id = payload.get("thread_id")
        row.po_number = payload.get("po_number")
        return

    if isinstance(row, ChatMessageCollection):
        row.session_id = payload.get("session_id")
        row.sender_id = payload.get("sender_id")
        return

    if isinstance(row, ChatUserMapCollection):
        row.internal_user_id = payload.get("internal_user_id")


def _seed_purchase_orders(session: Session, po_rows: List[Dict[str, Any]]) -> None:
    ps_rows = (
        session.query(User.id, User.name, User.email)
        .filter(User.role == "PROCUREMENT_SPECIALIST")
        .all()
    )
    ps_identity_to_id: Dict[str, str] = {}
    ps_ids: List[str] = []
    default_ps_id: Optional[str] = None
    site_to_ps_id: Dict[str, str] = {}

    for row in ps_rows:
        user_id = _safe_str(row.id)
        if not user_id:
            continue
        if default_ps_id is None:
            default_ps_id = user_id
        ps_ids.append(user_id)

        for identity in (row.id, row.name, row.email):
            identity_text = _safe_str(identity)
            if identity_text:
                ps_identity_to_id[identity_text.casefold()] = user_id

    for po_idx, order in enumerate(po_rows, start=1):
        po_header_id = _safe_str(order.get("id") or order.get("po_header_id") or order.get("po_number")) or str(uuid.uuid4())
        session.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_header_id == po_header_id).delete(synchronize_session=False)
        supplier_msid = _to_supplier_msid(_coalesce(order.get("supplier_msid"), order.get("local_supplier_id"), order.get("supplier_id")), 900000 + po_idx)
        location_id = _to_location_id(_coalesce(order.get("location_id"), order.get("site"), order.get("location")), 700000 + po_idx)
        site_key = (_safe_str(order.get("site")) or _safe_str(order.get("location")) or str(location_id)).casefold()
        raw_ps_identity = _safe_str(order.get("procurement_specialist_id"))
        procurement_specialist_id = None
        # Enforce one PS per site: once a site is assigned, reuse that PS for all its POs.
        if site_key in site_to_ps_id:
            procurement_specialist_id = site_to_ps_id[site_key]
        else:
            if raw_ps_identity:
                procurement_specialist_id = ps_identity_to_id.get(raw_ps_identity.casefold())
                if procurement_specialist_id is None and session.get(User, raw_ps_identity) is not None:
                    procurement_specialist_id = raw_ps_identity
                if procurement_specialist_id is None and ps_ids:
                    digest = hashlib.md5(raw_ps_identity.casefold().encode("utf-8")).hexdigest()
                    index = int(digest, 16) % len(ps_ids)
                    procurement_specialist_id = ps_ids[index]
            if procurement_specialist_id is None and ps_ids:
                digest = hashlib.md5(site_key.encode("utf-8")).hexdigest()
                index = int(digest, 16) % len(ps_ids)
                procurement_specialist_id = ps_ids[index]
        if procurement_specialist_id is None:
            procurement_specialist_id = default_ps_id
        if procurement_specialist_id:
            site_to_ps_id[site_key] = procurement_specialist_id

        if session.get(SupplierMaster, supplier_msid) is None:
            session.add(SupplierMaster(msid=supplier_msid, supplier_name=_safe_str(order.get("supplier_name")) or f"Supplier {supplier_msid}"))
        if session.get(LocationMaster, location_id) is None:
            session.add(
                LocationMaster(
                    location_id=location_id,
                    location_name=_safe_str(order.get("site") or order.get("location")) or f"Site-{location_id}",
                    platform="UNKNOWN",
                    iso_country_code="US",
                    sector="",
                    division="",
                    location_type="",
                    heritage_name="",
                    operating_model="",
                    platform_management_region="",
                    is_balanced_scorecard=False,
                    business_unit="",
                    ru_no="",
                    custom_bu="",
                )
            )

        # Ensure supplier/location parents exist before inserting item/PO child rows.
        session.flush()

        lines = order.get("line_items") if isinstance(order.get("line_items"), list) else []
        if not lines:
            lines = [{"line_number": 1, "material_code": f"MAT-{po_idx:04d}", "description": "Generated line item", "quantity": 1, "unit_price": 0.0}]

        for line_idx, line in enumerate(lines, start=1):
            item_no = _safe_str(line.get("item_no") or line.get("material_code")) or f"MAT-{po_idx:04d}-{line_idx:02d}"
            _ensure_item(session, item_no, location_id)

        # Ensure referenced items exist before inserting PO lines that FK to items.
        session.flush()

        for line_idx, line in enumerate(lines, start=1):
            item_no = _safe_str(line.get("item_no") or line.get("material_code")) or f"MAT-{po_idx:04d}-{line_idx:02d}"

            quantity = _safe_int(line.get("quantity") or line.get("quantity_ordered")) or 0
            unit_price = _safe_float(line.get("unit_price") or line.get("unit_cost")) or 0.0
            po_issue_date = _safe_date(
                _coalesce(
                    order.get("po_issue_date"),
                    order.get("created_date"),
                    order.get("period_date"),
                    line.get("po_line_issue_date"),
                    line.get("po_line_ack_date"),
                    line.get("erp_extract_date"),
                    line.get("original_promise_date"),
                    line.get("latest_promise_date"),
                    line.get("shipment_date"),
                    line.get("required_in_house_date"),
                    line.get("mrp_need_by_date"),
                    order.get("delivery_date"),
                )
            )
            po_line_issue_date = _safe_date(
                _coalesce(
                    line.get("po_line_issue_date"),
                    line.get("po_issue_date"),
                    order.get("po_issue_date"),
                    order.get("created_date"),
                    line.get("po_line_ack_date"),
                    line.get("erp_extract_date"),
                    line.get("original_promise_date"),
                    line.get("latest_promise_date"),
                    line.get("shipment_date"),
                    po_issue_date,
                )
            )

            session.add(
                PurchaseOrderLine(
                    po_header_id=po_header_id,
                    period_date=_safe_date(order.get("period_date")),
                    local_supplier_id=supplier_msid,
                    location_id=location_id,
                    source_erp=_safe_str(order.get("source_system") or order.get("source_erp")) or "SAP S4",
                    po_no=_safe_str(order.get("po_number") or order.get("po_no")),
                    poline_no=_safe_str(line.get("line_number") or line.get("po_line_no") or str(line_idx)),
                    po_release_no=_safe_int(line.get("po_release_no")),
                    po_line_revision_no=_safe_int(line.get("po_line_revision_no")),
                    po_issue_date=po_issue_date,
                    po_line_issue_date=po_line_issue_date,
                    po_status=_safe_str(order.get("status") or order.get("po_status")) or "Open",
                    item_no=item_no,
                    item_description=_safe_str(line.get("description") or line.get("item_description")),
                    quantity_ordered=quantity,
                    quantity_outstanding=_safe_int(line.get("quantity_outstanding")) or quantity,
                    unit_of_measure=_safe_str(line.get("unit") or line.get("unit_of_measure")),
                    unit_cost=unit_price,
                    currency_code=_safe_str(order.get("currency") or line.get("currency_code")) or "USD",
                    mrp_need_by_date=_safe_date(order.get("mrp_need_by_date") or line.get("mrp_need_by_date") or line.get("required_in_house_date")),
                    original_promise_date=_safe_date(line.get("original_promise_date") or line.get("latest_promise_date") or order.get("delivery_date")),
                    latest_promise_date=_safe_date(line.get("latest_promise_date") or order.get("delivery_date")),
                    ots_promise_date=_safe_date(line.get("ots_promise_date") or line.get("shipment_date") or order.get("delivery_date")),
                    item_category_id=_safe_str(line.get("item_category_id")),
                    incoterm=_safe_str(line.get("incoterm") or order.get("incoterm")),
                    incoterm_named_place=_safe_str(line.get("incoterm_named_place")),
                    payment_term=_safe_str(order.get("payment_terms") or order.get("payment_term")),
                    seals_ord_no=_safe_str(line.get("seals_ord_no")),
                    drawing_no=_safe_str(line.get("drawing_no")),
                    drawing_revision=_safe_str(line.get("drawing_revision")),
                    shipment_mode=_safe_str(line.get("shipment_mode")),
                    po_line_ack_status=_safe_str(line.get("po_line_ack_status") or line.get("po_line_ackn_status") or line.get("line_status")),
                    po_line_ack_date=_safe_date(line.get("po_line_ack_date") or line.get("po_line_ackn_dt")),
                    savings_type=_safe_str(line.get("savings_type")),
                    savings=_safe_int(line.get("savings")),
                    std_unit_cost=_safe_float(line.get("std_unit_cost")),
                    erp_extract_date=_safe_date(line.get("erp_extract_date") or line.get("erp_extract_dt")),
                    except_message=_safe_str(line.get("except_message") or order.get("mrp_exceptions")),
                    rescheduling_date=_safe_date(line.get("rescheduling_date") or line.get("mrp_need_by_date")),
                    po_feedback=_safe_str(line.get("po_feedback") or order.get("po_feedback")),
                    supplier_email=_safe_str(order.get("supplier_email") or line.get("supplier_email")),
                    purchasing_group=_safe_str(line.get("purchasing_group") or order.get("purchasing_group")),
                    procurement_specialist_id=procurement_specialist_id,
                    delegated_user_id=_safe_str(order.get("delegated_user_id")),
                    line_status=_safe_str(line.get("line_status")),
                    updated_quantity=_safe_float(line.get("updated_quantity")),
                    updated_unit_price=_safe_float(line.get("updated_unit_price")),
                    updated_delivery_date=_safe_date(line.get("updated_delivery_date")),
                    updated_material_no=_safe_str(line.get("updated_material_no")),
                    updated_description=_safe_str(line.get("updated_description")),
                    updated_net_value=_safe_float(line.get("updated_net_value")),
                    line_documents=line.get("documents") if isinstance(line.get("documents"), list) else [],
                    line_history=line.get("history") if isinstance(line.get("history"), list) else [],
                    split_deliveries=line.get("split_deliveries") if isinstance(line.get("split_deliveries"), list) else [],
                    concession_reason=_safe_str(line.get("concession_reason") or line.get("concession")),
                    concession_description=_safe_str(line.get("concession_description")),
                )
            )


def _seed_users(session: Session, user_rows: List[Dict[str, Any]]) -> None:
    for row in user_rows:
        user_id = _safe_str(row.get("id"))
        if not user_id:
            continue
        existing = session.get(User, user_id)
        user = existing or User(
            id=user_id,
            name=_safe_str(row.get("name")) or user_id,
            email=_safe_str(row.get("email")) or f"{user_id.lower()}@mockscm.com",
            role=_safe_str(row.get("role")) or "PROCUREMENT_SPECIALIST",
        )

        user.name = _safe_str(row.get("name")) or user.name
        user.email = _safe_str(row.get("email")) or user.email
        user.role = _safe_str(row.get("role")) or user.role
        user.password = _safe_str(row.get("password"))
        user.supplier_number = _safe_str(row.get("supplier_number"))
        user.phone = _safe_str(row.get("phone"))
        user.address = _safe_str(row.get("address"))
        user.site = _safe_str(row.get("site"))
        user.supplier_msid = _safe_int(row.get("supplier_msid"))
        user.pinned_rows = row.get("pinned_rows") if isinstance(row.get("pinned_rows"), list) else []
        user.line_pinned_rows = row.get("line_pinned_rows") if isinstance(row.get("line_pinned_rows"), list) else []
        user.metadata_json = row.get("data") if isinstance(row.get("data"), dict) else {}

        session.add(user)


def _seed_supplier_users(session: Session, supplier_rows: List[Dict[str, Any]]) -> None:
    default_supplier_password = "Password123"
    used_emails = {row[0] for row in session.query(User.email).all() if row[0]}

    for idx, row in enumerate(supplier_rows, start=1):
        user_id = _safe_str(row.get("id") or row.get("seed_user_id"))
        if not user_id:
            continue

        raw_email = _safe_str(row.get("email") or row.get("seed_email"))
        email = raw_email or f"{user_id.lower()}@mockscm.com"

        existing_user = session.get(User, user_id)
        existing_email = existing_user.email if existing_user is not None else None
        if existing_email:
            used_emails.discard(existing_email)

        if email in used_emails:
            email = f"{user_id.lower()}@mockscm.com"
        if email in used_emails:
            email = f"{user_id.lower()}_{idx}@mockscm.com"

        used_emails.add(email)

        msid = _to_supplier_msid(_coalesce(row.get("supplier_msid"), row.get("msid"), user_id), 800000 + idx)
        if session.get(SupplierMaster, msid) is None:
            session.add(SupplierMaster(msid=msid, supplier_name=_safe_str(row.get("name") or row.get("supplier_name")) or f"Supplier {msid}"))

        existing = existing_user
        user = existing or User(
            id=user_id,
            name=_safe_str(row.get("name") or row.get("supplier_name")) or user_id,
            email=email,
            role="SUPPLIER",
        )
        user.name = _safe_str(row.get("name") or row.get("supplier_name")) or user.name
        user.email = email
        user.role = "SUPPLIER"
        user.password = _safe_str(row.get("password")) or default_supplier_password
        user.address = _safe_str(row.get("address"))
        user.site = _safe_str(row.get("site"))
        user.supplier_msid = msid
        user.metadata_json = row.get("data") if isinstance(row.get("data"), dict) else {}

        session.add(user)


def _seed_delegations(session: Session, delegation_rows: List[Dict[str, Any]]) -> None:
    for row in delegation_rows:
        delegation_id = _safe_str(row.get("id")) or f"DEL-{uuid.uuid4().hex[:8].upper()}"
        delegated_from = _safe_str(row.get("delegated_from_id"))
        delegated_to = _safe_str(row.get("delegated_to_id"))
        if not delegated_from or not delegated_to:
            continue
        if session.get(User, delegated_from) is None or session.get(User, delegated_to) is None:
            continue

        existing = session.get(Delegation, delegation_id)
        delegation = existing or Delegation(
            id=delegation_id,
            po_id=_safe_str(row.get("po_id")) or "",
            delegated_from_id=delegated_from,
            delegated_to_id=delegated_to,
            status=_safe_str(row.get("status")) or "DRAFT",
        )
        delegation.po_id = _safe_str(row.get("po_id")) or delegation.po_id
        delegation.po_number = _safe_str(row.get("po_number"))
        delegation.supplier_name = _safe_str(row.get("supplier_name"))
        delegation.delegated_from_id = delegated_from
        delegation.delegated_to_id = delegated_to
        delegation.role = _safe_str(row.get("role"))
        delegation.start_date = _safe_date(row.get("start_date"))
        delegation.end_date = _safe_date(row.get("end_date"))
        delegation.status = _safe_str(row.get("status")) or delegation.status
        delegation.total_value = _safe_float(row.get("total_value"))
        delegation.created_date = _safe_datetime(row.get("created_date"))

        session.add(delegation)


def _seed_chat_tables(session: Session) -> None:
    for row in _load_json_records("chat_sessions.json"):
        row_id = _safe_str(row.get("id")) or str(uuid.uuid4())
        if session.get(ChatSession, row_id):
            continue
        session.add(
            ChatSession(
                id=row_id,
                chat_type=_safe_str(row.get("chat_type")) or "PS_SUPPLIER",
                po_id=_safe_str(row.get("po_id")),
                po_number=_safe_str(row.get("po_number")),
                participants=row.get("participants") if isinstance(row.get("participants"), list) else [],
                participants_signature=_safe_str(row.get("participants_signature")),
                created_by=_safe_str(row.get("created_by")),
                acs_thread_id=_safe_str(row.get("acs_thread_id")),
                acs_provider=_safe_str(row.get("acs_provider")),
                unread_count_by_user=row.get("unread_count_by_user") if isinstance(row.get("unread_count_by_user"), dict) else {},
                status=_safe_str(row.get("status")) or "ACTIVE",
                data=row,
                created_at=_safe_datetime(row.get("created_at")) or datetime.utcnow(),
                updated_at=_safe_datetime(row.get("updated_at")) or datetime.utcnow(),
            )
        )

    for row in _load_json_records("chat_messages.json"):
        row_id = _safe_str(row.get("id")) or str(uuid.uuid4())
        if session.get(ChatMessage, row_id):
            continue
        session.add(
            ChatMessage(
                id=row_id,
                session_id=_safe_str(row.get("session_id")) or "",
                sender_id=_safe_str(row.get("sender_id")) or "",
                data=row,
                created_at=_safe_datetime(row.get("created_at")) or datetime.utcnow(),
                updated_at=_safe_datetime(row.get("updated_at")) or datetime.utcnow(),
            )
        )

    for row in _load_json_records("chat_user_map.json"):
        row_id = _safe_str(row.get("id") or row.get("internal_user_id"))
        if not row_id or session.get(ChatUserMap, row_id):
            continue
        session.add(
            ChatUserMap(
                id=row_id,
                internal_user_id=_safe_str(row.get("internal_user_id")) or row_id,
                data=row,
                created_at=_safe_datetime(row.get("created_at")) or datetime.utcnow(),
                updated_at=_safe_datetime(row.get("updated_at")) or datetime.utcnow(),
            )
        )


def seed_relational_data(force_reset: bool = False) -> None:
    suppliers = _load_json_records("suppliers.json")
    locations = _load_json_records("locations.json")
    items = _load_json_records("items.json")
    purchase_orders = _load_json_records("purchase_orders.json")
    users = _load_json_records("users.json")
    delegations = _load_json_records("delegations.json")

    with _session_scope() as session:
        if force_reset:
            # Use TRUNCATE CASCADE to avoid FK-order sensitivity across environments.
            for table_name in [
                "po_line_splits",
                "po_status_history",
                "po_documents",
                "chat_messages",
                "chat_sessions",
                "chat_user_map",
                "delegations",
                "purchase_orders",
                "users",
                "items",
                "locations",
                "suppliers",
            ]:
                session.execute(text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE"))

        _seed_suppliers(session, suppliers)
        _seed_locations(session, locations)
        session.flush()

        _seed_items(session, items)
        session.flush()

        _seed_users(session, users)
        _seed_supplier_users(session, suppliers)
        session.flush()

        _seed_purchase_orders(session, purchase_orders)
        session.flush()

        _seed_delegations(session, delegations)
        _seed_chat_tables(session)


def _serialize_user(row: User) -> Dict[str, Any]:
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


def _serialize_delegation(row: Delegation) -> Dict[str, Any]:
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


def _serialize_chat_session(row: ChatSession) -> Dict[str, Any]:
    payload = dict(row.data or {})
    payload.update(
        {
            "id": row.id,
            "chat_type": row.chat_type,
            "po_id": row.po_id,
            "po_number": row.po_number,
            "participants": row.participants or [],
            "participants_signature": row.participants_signature,
            "created_by": row.created_by,
            "acs_thread_id": row.acs_thread_id,
            "acs_provider": row.acs_provider,
            "unread_count_by_user": row.unread_count_by_user or {},
            "status": row.status,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


def _serialize_chat_message(row: ChatMessage) -> Dict[str, Any]:
    payload = dict(row.data or {})
    payload.update(
        {
            "id": row.id,
            "session_id": row.session_id,
            "sender_id": row.sender_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


def _serialize_chat_user_map(row: ChatUserMap) -> Dict[str, Any]:
    payload = dict(row.data or {})
    payload.update(
        {
            "id": row.id,
            "internal_user_id": row.internal_user_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


def _serialize_po_line(line: PurchaseOrderLine) -> Dict[str, Any]:
    quantity = line.updated_quantity if line.updated_quantity is not None else (line.quantity_ordered or 0)
    unit_cost = float(line.updated_unit_price if line.updated_unit_price is not None else (line.unit_cost or 0.0))
    net_value = round(quantity * unit_cost, 2)
    line_number = _safe_str(line.poline_no) or ""
    return {
        "id": str(line.po_id),
        "line_number": line_number.zfill(8) if line_number.isdigit() else line_number,
        "po_line_no": line.poline_no,
        "po_release_no": line.po_release_no,
        "po_line_revision_no": line.po_line_revision_no,
        "po_line_issue_date": line.po_line_issue_date.isoformat() if line.po_line_issue_date else None,
        "item_no": line.item_no,
        "material_code": (line.item.material_code if line.item and line.item.material_code else line.item_no),
        "description": line.item_description,
        "quantity": quantity,
        "quantity_outstanding": line.quantity_outstanding,
        "unit_price": unit_cost,
        "currency_code": line.currency_code,
        "unit": line.unit_of_measure,
        "shipment_date": line.ots_promise_date.isoformat() if line.ots_promise_date else None,
        "original_promise_date": line.original_promise_date.isoformat() if line.original_promise_date else None,
        "latest_promise_date": line.latest_promise_date.isoformat() if line.latest_promise_date else None,
        "required_in_house_date": line.mrp_need_by_date.isoformat() if line.mrp_need_by_date else None,
        "net_value": net_value,
        "item_category_id": line.item_category_id,
        "incoterm": line.incoterm,
        "incoterm_named_place": line.incoterm_named_place,
        "payment_term": line.payment_term,
        "supplier_email": line.supplier_email,
        "purchasing_group": line.purchasing_group,
        "shipment_mode": line.shipment_mode,
        "po_line_ack_status": line.po_line_ack_status,
        "po_line_ack_date": line.po_line_ack_date.isoformat() if line.po_line_ack_date else None,
        "savings_type": line.savings_type,
        "savings": line.savings,
        "std_unit_cost": line.std_unit_cost,
        "erp_extract_date": line.erp_extract_date.isoformat() if line.erp_extract_date else None,
        "except_message": line.except_message,
        "rescheduling_date": line.rescheduling_date.isoformat() if line.rescheduling_date else None,
        "po_feedback": line.po_feedback,
        "drawing_no": line.drawing_no,
        "drawing_revision": line.drawing_revision,
        "seals_ord_no": line.seals_ord_no,
        "line_status": line.line_status or line.po_line_ack_status or "",
        "updated_quantity": line.updated_quantity,
        "updated_unit_price": line.updated_unit_price,
        "updated_delivery_date": line.updated_delivery_date.isoformat() if line.updated_delivery_date else None,
        "updated_material_no": line.updated_material_no,
        "updated_description": line.updated_description,
        "updated_net_value": line.updated_net_value,
        "documents": line.line_documents or [],
        "history": line.line_history or [],
        "split_deliveries": line.split_deliveries or [],
        "concession": line.concession_reason,
        "concession_description": line.concession_description,
    }


def _build_po_payload(first_line: PurchaseOrderLine) -> Dict[str, Any]:
    supplier_name = first_line.supplier.supplier_name if first_line.supplier else None
    site_name = first_line.location.location_name if first_line.location else None
    created_date = (
        first_line.po_issue_date
        or first_line.po_line_issue_date
        or first_line.period_date
        or first_line.erp_extract_date
        or first_line.original_promise_date
        or first_line.latest_promise_date
        or first_line.ots_promise_date
        or first_line.mrp_need_by_date
    )
    last_modified_date = (
        first_line.updated_delivery_date
        or first_line.po_line_ack_date
        or first_line.rescheduling_date
        or first_line.latest_promise_date
        or first_line.ots_promise_date
        or first_line.erp_extract_date
        or created_date
    )
    return {
        "id": first_line.po_header_id,
        "po_number": first_line.po_no,
        "supplier_msid": first_line.local_supplier_id,
        "supplier_id": str(first_line.local_supplier_id),
        "supplier_name": supplier_name,
        "supplier_email": first_line.supplier_email,
        "site": site_name,
        "status": first_line.po_status,
        "source_system": first_line.source_erp,
        "currency": first_line.currency_code,
        "payment_terms": first_line.payment_term,
        "delivery_date": first_line.latest_promise_date.isoformat() if first_line.latest_promise_date else None,
        "mrp_need_by_date": first_line.mrp_need_by_date.isoformat() if first_line.mrp_need_by_date else None,
        "procurement_specialist_id": first_line.procurement_specialist_id,
        "delegated_user_id": first_line.delegated_user_id,
        "created_date": created_date.isoformat() if created_date else None,
        "last_modified_by": first_line.procurement_specialist_id or first_line.delegated_user_id or "SYSTEM",
        "last_modified_date": last_modified_date.isoformat() if last_modified_date else None,
        "period_date": first_line.period_date.isoformat() if first_line.period_date else None,
        "purchasing_group": first_line.purchasing_group,
        "mrp_exceptions": first_line.except_message,
        "line_items": [],
        "status_history": [],
        "workflow_stage": "PO_DETAILS",
        "revision_changes": 0,
    }


def query_relational_purchase_orders() -> List[Dict[str, Any]]:
    with _session_scope() as session:
        rows = (
            session.query(PurchaseOrderLine)
            .order_by(PurchaseOrderLine.po_header_id, PurchaseOrderLine.poline_no)
            .all()
        )
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            po = grouped.get(row.po_header_id)
            if po is None:
                po = _build_po_payload(row)
                grouped[row.po_header_id] = po
            po["line_items"].append(_serialize_po_line(row))

        for po in grouped.values():
            po["total_value"] = round(sum(line.get("net_value", 0) for line in po.get("line_items", [])), 2)

        return list(grouped.values())


def find_relational_purchase_order(po_id: str) -> Optional[Dict[str, Any]]:
    with _session_scope() as session:
        rows = (
            session.query(PurchaseOrderLine)
            .filter(PurchaseOrderLine.po_header_id == po_id)
            .order_by(PurchaseOrderLine.poline_no)
            .all()
        )
        if not rows:
            return None

        po = _build_po_payload(rows[0])
        po["line_items"] = [_serialize_po_line(row) for row in rows]
        po["total_value"] = round(sum(line.get("net_value", 0) for line in po.get("line_items", [])), 2)
        return po


def _upsert_po_document(session: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    po_id = _safe_str(payload.get("id")) or str(uuid.uuid4())
    session.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_header_id == po_id).delete()
    session.flush()

    po_payload = dict(payload)
    po_payload["id"] = po_id
    _seed_purchase_orders(session, [po_payload])
    session.flush()

    return find_relational_purchase_order(po_id) or po_payload


def create_relational_purchase_order(document: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(document)
    payload.setdefault("id", str(uuid.uuid4()))

    with _session_scope() as session:
        existing = (
            session.query(PurchaseOrderLine)
            .filter(PurchaseOrderLine.po_header_id == payload["id"])
            .first()
        )
        if existing is not None:
            raise ValueError(f"Purchase order '{payload['id']}' already exists")
        return _upsert_po_document(session, payload)


def replace_relational_purchase_order(po_id: str, document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = dict(document)
    payload["id"] = po_id

    with _session_scope() as session:
        existing = (
            session.query(PurchaseOrderLine)
            .filter(PurchaseOrderLine.po_header_id == po_id)
            .first()
        )
        if existing is None:
            return None
        return _upsert_po_document(session, payload)


def ensure_canonical_json() -> None:
    canonical_po = CANONICAL_DIR / "purchase_orders.canonical.json"
    if canonical_po.exists():
        return
    source_po = DATA_DIR / "purchase_orders.json"
    if not source_po.exists():
        return
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    with source_po.open("r", encoding="utf-8-sig") as input_file:
        payload = json.load(input_file)
    with canonical_po.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2)


def _hydrate_runtime_from_canonical_if_needed() -> None:
    ensure_canonical_json()
    canonical_po = CANONICAL_DIR / "purchase_orders.canonical.json"
    if canonical_po.exists():
        with canonical_po.open("r", encoding="utf-8-sig") as input_file:
            payload = json.load(input_file)
        with (DATA_DIR / "purchase_orders.json").open("w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, indent=2)


def initialize_database() -> None:
    from app.db import models as _models  # noqa: F401

    regenerate_purchase_orders_json_from_xlsx()
    _hydrate_runtime_from_canonical_if_needed()
    _ensure_database_exists()
    Base.metadata.create_all(bind=engine)
    seed_relational_data(force_reset=False)


def find_one(collection_name: str, filter_value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    items = query_items(collection_name, filter_value)
    return items[0] if items else None


def find_many(collection_name: str, filter_value: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return query_items(collection_name, filter_value)

def insert_one(collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model(collection_name)
    payload = _clean_document(document) or {}

    with _session_scope() as session:
        row = _build_row(model, payload)
        session.add(row)

    logger.info("postgres.insert_one collection=%s id=%s", collection_name, payload.get("id"))
    return payload

def query_items(collection_name: str, filter_value: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    model = _get_model(collection_name)
    normalized = _normalize_filter(filter_value)

    with _session_scope() as session:
        rows = session.query(model).all()
        documents = [_row_to_document(row) for row in rows]
        if not normalized:
            return documents
        return [document for document in documents if _matches_filter(document, normalized)]

def _get_model(collection_name: str) -> CollectionModel:
    model = COLLECTION_MODELS.get(collection_name)
    if not model:
        raise ValueError(f"Unsupported collection '{collection_name}'")
    return model

def _normalize_filter(filter_value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if not filter_value:
        return normalized

    for key, value in filter_value.items():
        normalized_key = "id" if key == "_id" else key
        normalized[normalized_key] = value
    return normalized


def _clean_document(document: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if document is None:
        return None
    cleaned = dict(document)
    cleaned.pop("_id", None)
    return cleaned

def _build_row(model: CollectionModel, payload: Dict[str, Any]) -> Any:
    row_id = payload.get("id") or str(uuid.uuid4())
    payload["id"] = row_id
    row = model(id=row_id, data=payload)
    _apply_index_fields(row, payload)
    return row

def _apply_index_fields(row: Any, payload: Dict[str, Any]) -> None:
    if isinstance(row, UserCollection):
        row.email = payload.get("email")
        row.role = payload.get("role")
        row.name = payload.get("name")
        return

    if isinstance(row, SupplierCollection):
        row.email = payload.get("email")
        row.role = payload.get("role")
        row.name = payload.get("name")
        return

    if isinstance(row, PurchaseOrderCollection):
        row.po_number = payload.get("po_number")
        row.status = payload.get("status")
        row.supplier_id = payload.get("supplier_id")
        row.procurement_specialist_id = payload.get("procurement_specialist_id")
        row.delivery_date = payload.get("delivery_date")
        row.mrp_need_by_date = _safe_date(payload.get("mrp_need_by_date"))
        return

    if isinstance(row, DelegationCollection):
        row.status = payload.get("status")
        row.delegated_from_id = payload.get("delegated_from_id")
        row.delegated_to_id = payload.get("delegated_to_id")
        row.po_id = payload.get("po_id")
        return

    if isinstance(row, ChatSessionCollection):
        row.po_id = payload.get("po_id")
        row.status = payload.get("status")
        row.chat_type = payload.get("chat_type")
        return

    if isinstance(row, ACSChatCollection):
        row.thread_id = payload.get("thread_id")
        row.po_number = payload.get("po_number")
        return

    if isinstance(row, ChatMessageCollection):
        row.session_id = payload.get("session_id")
        row.sender_id = payload.get("sender_id")
        return

    if isinstance(row, ChatUserMapCollection):
        row.internal_user_id = payload.get("internal_user_id")


def _row_to_document(row: Any) -> Dict[str, Any]:
    payload = dict(row.data or {})
    payload["id"] = row.id
    return _clean_document(payload) or {}