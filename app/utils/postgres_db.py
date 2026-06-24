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
    SupplierCollection,
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
