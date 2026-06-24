import json
import logging
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type

from sqlalchemy.orm import Session

from app.db.models import (
    ChatMessageCollection,
    ChatSessionCollection,
    ChatUserMapCollection,
    DelegationCollection,
    PurchaseOrderCollection,
    PurchaseOrderLine,
    SupplierCollection,
    SupplierMaster,
    LocationMaster,
    ItemMaster,
    UserCollection,
)
from app.db.session import Base, SessionLocal, engine

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

logger = logging.getLogger(__name__)

CollectionModel = Type[
    UserCollection
    | SupplierCollection
    | PurchaseOrderCollection
    | DelegationCollection
    | ChatSessionCollection
    | ChatMessageCollection
    | ChatUserMapCollection
]

COLLECTION_MODELS: Dict[str, CollectionModel] = {
    "users": UserCollection,
    "suppliers": SupplierCollection,
    "purchase_orders": PurchaseOrderCollection,
    "delegations": DelegationCollection,
    "chat_sessions": ChatSessionCollection,
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


def _row_to_document(row: Any) -> Dict[str, Any]:
    payload = dict(row.data or {})
    payload["id"] = row.id
    return _clean_document(payload) or {}


def _matches_filter(document: Dict[str, Any], filter_value: Dict[str, Any]) -> bool:
    for key, expected in filter_value.items():
        if document.get(key) != expected:
            return False
    return True


def _safe_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(value))
    except Exception:
        return None


def _safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "t"}:
        return True
    if normalized in {"0", "false", "no", "n", "f"}:
        return False
    return None


def _json_load(file_path: Path) -> Any:
    with open(file_path, "r", encoding="utf-8-sig") as input_file:
        return json.load(input_file)


def _seed_supplier_master() -> None:
    file_path = DATA_DIR / "suppliers.json"
    if not file_path.exists():
        return

    with _session_scope() as session:
        if session.query(SupplierMaster).count() > 0:
            return

        raw_records = _json_load(file_path)
        for data in raw_records:
            row = SupplierMaster(
                    msid=str(data.get("msid") or data.get("local_supplier_id") or data.get("id") or ""),
                    supplier_name=str(data.get("name") or data.get("supplier_name") or "").strip(),
                    supplier_dba_name=str(data.get("supplier_dba_name") or "").strip(),
                    category_id=str(data.get("category_id") or "").strip(),
                    category_id2=str(data.get("category_id2") or "").strip(),
                    slp_id=str(data.get("slp_id") or "").strip(),
                    address=str(data.get("address") or "").strip(),
                    city=str(data.get("city") or "").strip(),
                    state_province=str(data.get("state_province") or "").strip(),
                    iso_country_code=str(data.get("iso_country_code") or "").strip(),
                    postal_code=str(data.get("postal_code") or "").strip(),
                    payment_term=str(data.get("payment_term") or "").strip(),
                    incoterm=str(data.get("incoterm") or "").strip(),
                    approval_status=str(data.get("approval_status") or "").strip(),
                    assigned_sqe=str(data.get("assigned_sqe") or "").strip(),
                    supplier_manager=str(data.get("supplier_manager") or "").strip(),
                    is_archived=_safe_bool(data.get("is_archived")) or False,
            )
            session.add(row)


def _seed_location_master() -> None:
    file_path = DATA_DIR / "locations.json"
    if not file_path.exists():
        return

    with _session_scope() as session:
        if session.query(LocationMaster).count() > 0:
            return

        raw_records = _json_load(file_path)
        for data in raw_records:
            row = LocationMaster(
                location_id=str(data.get("location_id") or data.get("location")),
                location_name=data.get("location_name") or data.get("location"),
                platform=data.get("platform") or data.get("site_type"),
                iso_country_code=data.get("iso_country_code"),
                address=data.get("address"),
                city=data.get("city"),
                state_province=data.get("state_province"),
                postal_code=data.get("postal_code"),
                operation=data.get("operation"),
                sector=data.get("sector"),
                division=data.get("division"),
                is_archived=_safe_bool(data.get("is_archived")),
            )
            session.add(row)


def _seed_item_master() -> None:
    file_path = DATA_DIR / "items.json"
    if not file_path.exists():
        return

    with _session_scope() as session:
        if session.query(ItemMaster).count() > 0:
            return

        raw_records = _json_load(file_path)
        for data in raw_records:
            row = ItemMaster(
                item_no=str(data.get("item_no") or data.get("material_code") or ""),
                location_id=str(data.get("location_id") or data.get("location") or ""),
                material_code=str(data.get("material_code") or "").strip(),
                item_lead_time=_safe_int(data.get("item_le_time") or data.get("item_lead_time")) or 0,
                item_weight=float(data.get("item_weight")) if data.get("item_weight") not in (None, "") else 0.0,
                item_weight_unit=str(data.get("item_weight_unit") or "EA").strip(),
                is_active=_safe_bool(data.get("is_active")) if _safe_bool(data.get("is_active")) is not None else True,
                is_safety_stock=_safe_bool(data.get("is_safety_stock")) if _safe_bool(data.get("is_safety_stock")) is not None else False,
                safety_stock_min=_safe_int(data.get("safety_stock_min")) or 0,
                safety_stock_max=_safe_int(data.get("safety_stock_max")) or 0,
            )
            session.add(row)


def _seed_purchase_order_lines() -> None:
    file_path = DATA_DIR / "purchase_orders.json"
    if not file_path.exists():
        return

    with _session_scope() as session:
        if session.query(PurchaseOrderLine).count() > 0:
            return

        raw_records = _json_load(file_path)
        for order in raw_records:
            po_header_id = str(order.get("id") or order.get("po_header_id") or order.get("po_number") or "")
            for line in order.get("line_items", []):
                _loc = str(order.get("location_id") or order.get("location") or "").strip()
                po_kwargs = {
                    "po_header_id": po_header_id,
                    "po_number": str(order.get("po_number") or ""),
                    "local_supplier_id": str(order.get("supplier_msid") or order.get("local_supplier_id") or order.get("supplier_id")) if order.get("supplier_msid") or order.get("local_supplier_id") or order.get("supplier_id") else None,
                }
                if _loc:
                    po_kwargs["location_id"] = _loc
                row = PurchaseOrderLine(
                    **po_kwargs,
                    source_erp=order.get("source_system") or order.get("source_erp") or "SAP",
                    po_line_no=str(line.get("line_number") or line.get("po_line_no") or ""),
                    po_release_no=_safe_int(line.get("po_release_no") or line.get("release_number")),
                    po_line_revision_no=_safe_int(line.get("po_line_revision_no") or line.get("revision_number")),
                    po_issue_date=_safe_date(order.get("po_issue_date") or order.get("created_date") or order.get("document_date")),
                    po_line_issue_date=_safe_date(line.get("po_line_issue_date") or line.get("line_issue_date") or order.get("created_date")),
                    po_created_by=order.get("procurement_specialist_id") or order.get("po_created_by"),
                    po_status=order.get("status") or order.get("po_status") or "OPEN",
                    item_no=str(line.get("item_no") or line.get("material_code") or ""),
                    item_description=line.get("description") or line.get("item_description"),
                    quantity_ordered=_safe_int(line.get("quantity") or line.get("quantity_ordered") or 0) or 0,
                    quantity_outstanding=_safe_int(line.get("quantity") or line.get("quantity_outstanding") or 0) or 0,
                    unit_of_measure=line.get("unit") or line.get("unit_of_measure"),
                    unit_cost=float(line.get("unit_price") or line.get("unit_cost") or 0.0),
                    currency_code=order.get("currency") or line.get("currency_code") or "USD",
                    mrp_need_by_date=_safe_date(line.get("mrp_need_by_date") or order.get("mrp_need_by_date") or order.get("delivery_date")),
                    original_promise_date=_safe_date(line.get("original_promise_date") or order.get("created_date") or order.get("document_date")),
                    latest_promise_date=_safe_date(line.get("latest_promise_date") or order.get("delivery_date") or line.get("latest_promise_date")),
                    ots_promise_date=_safe_date(line.get("ots_promise_date") or line.get("shipment_date") or order.get("shipment_date")),
                    item_category_id=line.get("item_category_id"),
                    incoterm=line.get("incoterm"),
                    incoterm_named_place=line.get("incoterm_named_place"),
                    payment_term=order.get("payment_terms") or order.get("payment_term"),
                    supplier_email=order.get("supplier_email") or line.get("supplier_email"),
                    purchasing_group=order.get("purchasing_group") or line.get("purchasing_group"),
                    shipment_mode=line.get("shipment_mode"),
                    po_line_ack_status=line.get("po_line_ack_status"),
                    po_line_ack_date=_safe_date(line.get("po_line_ack_date")),
                    savings_type=line.get("savings_type"),
                    savings=_safe_int(line.get("savings")),
                    std_unit_cost=float(line.get("std_unit_cost") or 0.0) if line.get("std_unit_cost") else None,
                    except_message=line.get("except_message"),
                    rescheduling_date=_safe_date(line.get("rescheduling_date")),
                    po_feedback=line.get("po_feedback"),
                )
                session.add(row)


def _seed_relational_data() -> None:
    _seed_supplier_master()
    _seed_location_master()
    _seed_item_master()
    _seed_purchase_order_lines()


def _serialize_po_line(line: PurchaseOrderLine) -> Dict[str, Any]:
    return {
        "id": str(line.id),
        "line_number": line.po_line_no or "",
        "item_no": line.item_no,
        "material_code": line.item_no,
        "description": line.item_description,
        "quantity": line.quantity_ordered,
        "unit_price": float(line.unit_cost or 0),
        "unit": line.unit_of_measure,
        "shipment_date": line.ots_promise_date.isoformat() if line.ots_promise_date else None,
        "required_in_house_date": line.mrp_need_by_date.isoformat() if line.mrp_need_by_date else None,
        "net_value": round((line.quantity_ordered or 0) * float(line.unit_cost or 0), 2),
        "item_category_id": line.item_category_id,
        "incoterm": line.incoterm,
        "incoterm_named_place": line.incoterm_named_place,
        "payment_term": line.payment_term,
        "supplier_email": line.supplier_email,
        "purchasing_group": line.purchasing_group,
        "line_status": line.po_line_ack_status or "",
        "history": [],
    }


def _build_relational_po(line: PurchaseOrderLine) -> Dict[str, Any]:
    supplier_name = line.supplier.supplier_name if line.supplier else None
    supplier_email = line.supplier_email or (line.supplier.supplier_name if line.supplier else None)
    site = line.location.location_name if line.location else None
    return {
        "id": line.po_header_id,
        "po_number": line.po_number,
        "supplier_id": str(line.local_supplier_id) if line.local_supplier_id is not None else None,
        "supplier_name": supplier_name,
        "supplier_email": supplier_email,
        "site": site,
        "status": line.po_status,
        "source_system": line.source_erp,
        "currency": line.currency_code,
        "payment_terms": line.payment_term,
        "delivery_date": line.latest_promise_date.isoformat() if line.latest_promise_date else None,
        "mrp_need_by_date": line.mrp_need_by_date.isoformat() if line.mrp_need_by_date else None,
        "procurement_specialist_id": line.po_created_by,
        "created_date": line.po_issue_date.isoformat() if line.po_issue_date else None,
        "line_items": [],
        "status_history": [],
        "workflow_stage": "PO_DETAILS",
    }


def query_relational_purchase_orders() -> List[Dict[str, Any]]:
    with _session_scope() as session:
        rows = session.query(PurchaseOrderLine).order_by(PurchaseOrderLine.po_header_id).all()

        pos_by_header: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            header_id = row.po_header_id
            po = pos_by_header.get(header_id)
            if po is None:
                po = _build_relational_po(row)
                pos_by_header[header_id] = po
            po.setdefault("line_items", []).append(_serialize_po_line(row))

        for po in pos_by_header.values():
            po["total_value"] = round(sum(item.get("net_value", 0) for item in po.get("line_items", [])), 2)

        return list(pos_by_header.values())


def find_relational_purchase_order(po_id: str) -> Optional[Dict[str, Any]]:
    with _session_scope() as session:
        rows = (
            session.query(PurchaseOrderLine)
            .filter(PurchaseOrderLine.po_header_id == po_id)
            .order_by(PurchaseOrderLine.po_line_no)
            .all()
        )

        if not rows:
            return None

        po = _build_relational_po(rows[0])
        po["line_items"] = [_serialize_po_line(row) for row in rows]
        po["total_value"] = round(sum(item.get("net_value", 0) for item in po.get("line_items", [])), 2)
        return po


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

    if isinstance(row, ChatMessageCollection):
        row.session_id = payload.get("session_id")
        row.sender_id = payload.get("sender_id")
        return

    if isinstance(row, ChatUserMapCollection):
        row.internal_user_id = payload.get("internal_user_id")


def _build_row(model: CollectionModel, payload: Dict[str, Any]) -> Any:
    row_id = payload.get("id") or str(uuid.uuid4())
    payload["id"] = row_id
    row = model(id=row_id, data=payload)
    _apply_index_fields(row, payload)
    return row


def query_items(collection_name: str, filter_value: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    model = _get_model(collection_name)
    normalized = _normalize_filter(filter_value)

    with _session_scope() as session:
        rows = session.query(model).all()
        documents = [_row_to_document(row) for row in rows]
        if not normalized:
            return documents
        return [document for document in documents if _matches_filter(document, normalized)]


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


def replace_one(collection_name: str, filter_value: Dict[str, Any], document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    model = _get_model(collection_name)
    normalized = _normalize_filter(filter_value)
    payload = _clean_document(document) or {}

    with _session_scope() as session:
        rows = session.query(model).all()
        target = None
        for row in rows:
            current = _row_to_document(row)
            if _matches_filter(current, normalized):
                target = row
                break

        if target is None:
            logger.warning("postgres.replace_one no_match collection=%s filter=%s", collection_name, normalized)
            return None

        payload["id"] = payload.get("id") or target.id
        target.id = payload["id"]
        target.data = payload
        _apply_index_fields(target, payload)

    logger.info("postgres.replace_one collection=%s id=%s", collection_name, payload.get("id"))
    return payload


def upsert_one(collection_name: str, filter_value: Dict[str, Any], document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    replaced = replace_one(collection_name, filter_value, document)
    if replaced is not None:
        return replaced
    return insert_one(collection_name, document)


def update_one(collection_name: str, filter_value: Dict[str, Any], update_value: Dict[str, Any]) -> int:
    model = _get_model(collection_name)
    normalized = _normalize_filter(filter_value)
    modified_count = 0

    with _session_scope() as session:
        rows = session.query(model).all()
        for row in rows:
            current = _row_to_document(row)
            if not _matches_filter(current, normalized):
                continue

            updated = dict(current)
            updated.update(update_value)
            row.data = updated
            _apply_index_fields(row, updated)
            modified_count += 1

    logger.info("postgres.update_one collection=%s modified=%s", collection_name, modified_count)
    return modified_count


def delete_one(collection_name: str, filter_value: Dict[str, Any]) -> int:
    model = _get_model(collection_name)
    normalized = _normalize_filter(filter_value)
    deleted_count = 0

    with _session_scope() as session:
        rows = session.query(model).all()
        for row in rows:
            current = _row_to_document(row)
            if not _matches_filter(current, normalized):
                continue
            session.delete(row)
            deleted_count += 1
            break

    logger.info("postgres.delete_one collection=%s deleted=%s", collection_name, deleted_count)
    return deleted_count


def count_documents(collection_name: str, filter_value: Optional[Dict[str, Any]] = None) -> int:
    return len(query_items(collection_name, filter_value))


def seed_collection(collection_name: str, file_name: str) -> None:
    file_path = DATA_DIR / file_name
    if not file_path.exists():
        return

    if count_documents(collection_name) > 0:
        return

    with open(file_path, "r", encoding="utf-8-sig") as input_file:
        data = json.load(input_file)

    if isinstance(data, dict):
        raw_documents: List[Dict[str, Any]] = [data]
    elif isinstance(data, list):
        raw_documents = data
    else:
        return

    seeded = 0
    for document in raw_documents:
        payload = dict(document)
        payload.setdefault("id", str(uuid.uuid4()))
        insert_one(collection_name, payload)
        seeded += 1

    logger.info("postgres.seed collection=%s records=%s", collection_name, seeded)


def initialize_database() -> None:
    # Ensure model metadata is imported before table creation.
    from app.db import models as _models  # noqa: F401
    from app.db.session import DATABASE_URL

    excel_path = os.getenv("OPEN_PO_EXCEL_PATH")
    if excel_path:
        excel_file = Path(excel_path)
        script_path = BASE_DIR / "scripts" / "seed_purchase_orders_from_excel.py"
        if excel_file.exists() and script_path.exists():
            try:
                logger.info("Generating purchase_orders.json from Excel: %s", excel_file)
                subprocess.run(
                    [
                        sys.executable,
                        str(script_path),
                        str(excel_file),
                        "--output",
                        str(DATA_DIR / "purchase_orders.json"),
                    ],
                    check=True,
                )
            except Exception as exc:
                logger.warning("Failed to generate purchase_orders.json from Excel: %s", exc)
        elif excel_path and not excel_file.exists():
            logger.warning("OPEN_PO_EXCEL_PATH does not exist: %s", excel_file)
        elif not script_path.exists():
            logger.warning("Seed generation script not found: %s", script_path)

    # If using PostgreSQL, create the database if it doesn't exist
    if "postgresql" in DATABASE_URL:
        try:
            from sqlalchemy import create_engine, text, event

            # Extract database name and connection params
            url_parts = DATABASE_URL.split("/")
            db_name = url_parts[-1]
            server_url = "/".join(url_parts[:-1]) + "/postgres"  # Connect to default 'postgres' db

            # Create engine for server connection
            server_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")

            with server_engine.connect() as conn:
                # Check if database exists
                result = conn.execute(
                    text(
                        f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"
                    )
                )
                if not result.fetchone():
                    logger.info(f"Creating database '{db_name}'...")
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    logger.info(f"Database '{db_name}' created successfully")
            server_engine.dispose()
        except Exception as exc:
            logger.warning(
                f"Could not ensure database exists: {exc}. "
                "Make sure the PostgreSQL database is created manually."
            )

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        raise RuntimeError(
            "Unable to initialize PostgreSQL schema. Set DATABASE_URL to a valid Postgres DSN."
        ) from exc

    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            for table, column in (
                ("purchase_orders", "mrp_need_by_date"),
                ("po_status_history", "move_in_date"),
                ("po_status_history", "move_out_date"),
                ("po_line_splits", "delivery_date"),
            ):
                try:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL"
                        )
                    )
                except Exception:
                    continue
    except Exception as exc:
        logger.warning("Could not relax nullable constraints: %s", exc)

    default_mappings = {
        "users": "users.json",
        "suppliers": "suppliers.json",
        "purchase_orders": "purchase_orders.json",
        "delegations": "delegations.json",
    }

    for collection_name, file_name in default_mappings.items():
        seed_collection(collection_name, file_name)

    optional_mappings = {
        "chat_sessions": "chat_sessions.json",
        "chat_messages": "chat_messages.json",
        "chat_user_map": "chat_user_map.json",
    }
    for collection_name, file_name in optional_mappings.items():
        seed_collection(collection_name, file_name)

    _seed_relational_data()
