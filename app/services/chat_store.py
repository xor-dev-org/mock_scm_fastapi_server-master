import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.db.models import ChatMessage, ChatSession, ChatUserMap, User
from app.db.session import SessionLocal
from app.utils.postgres_db import find_relational_purchase_order, query_relational_purchase_orders

CHAT_SESSIONS_COLLECTION = os.getenv("CHAT_SESSIONS_COLLECTION", "chat_sessions")
CHAT_MESSAGES_COLLECTION = os.getenv("CHAT_MESSAGES_COLLECTION", "chat_messages")
CHAT_USER_MAP_COLLECTION = os.getenv("CHAT_USER_MAP_COLLECTION", "chat_user_map")
USERS_COLLECTION = os.getenv("USERS_COLLECTION", "users")
SUPPLIERS_COLLECTION = os.getenv("SUPPLIERS_COLLECTION", "suppliers")
PURCHASE_ORDERS_COLLECTION = os.getenv("PURCHASE_ORDERS_COLLECTION", "purchase_orders")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sessions() -> List[Dict]:
    session = SessionLocal()
    try:
        rows = session.query(ChatSession).all()
        out: List[Dict] = []
        for row in rows:
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
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            )
            out.append(payload)
        return out
    finally:
        session.close()


def save_sessions(sessions: List[Dict]) -> None:
    db = SessionLocal()
    try:
        for session in sessions:
            payload = dict(session)
            payload.setdefault("id", str(uuid.uuid4()))

            row = db.get(ChatSession, payload["id"])
            if not row:
                row = ChatSession(
                    id=payload["id"],
                    chat_type=payload.get("chat_type") or "PS_SUPPLIER",
                    po_id=payload.get("po_id"),
                    po_number=payload.get("po_number"),
                    participants=payload.get("participants") if isinstance(payload.get("participants"), list) else [],
                    participants_signature=payload.get("participants_signature"),
                    created_by=payload.get("created_by"),
                    acs_thread_id=payload.get("acs_thread_id"),
                    acs_provider=payload.get("acs_provider"),
                    unread_count_by_user=payload.get("unread_count_by_user") if isinstance(payload.get("unread_count_by_user"), dict) else {},
                    status=payload.get("status") or "ACTIVE",
                    data=payload,
                )
            else:
                row.chat_type = payload.get("chat_type") or row.chat_type
                row.po_id = payload.get("po_id")
                row.po_number = payload.get("po_number")
                row.participants = payload.get("participants") if isinstance(payload.get("participants"), list) else row.participants
                row.participants_signature = payload.get("participants_signature")
                row.created_by = payload.get("created_by")
                row.acs_thread_id = payload.get("acs_thread_id")
                row.acs_provider = payload.get("acs_provider")
                row.unread_count_by_user = payload.get("unread_count_by_user") if isinstance(payload.get("unread_count_by_user"), dict) else row.unread_count_by_user
                row.status = payload.get("status") or row.status
                row.data = payload

            db.add(row)
        db.commit()
    finally:
        db.close()


def load_messages() -> List[Dict]:
    session = SessionLocal()
    try:
        rows = session.query(ChatMessage).all()
        out: List[Dict] = []
        for row in rows:
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
            out.append(payload)
        return out
    finally:
        session.close()


def save_messages(messages: List[Dict]) -> None:
    db = SessionLocal()
    try:
        for message in messages:
            payload = dict(message)
            payload.setdefault("id", str(uuid.uuid4()))

            row = db.get(ChatMessage, payload["id"])
            if not row:
                row = ChatMessage(
                    id=payload["id"],
                    session_id=payload.get("session_id") or "",
                    sender_id=payload.get("sender_id") or "",
                    data=payload,
                )
            else:
                row.session_id = payload.get("session_id") or row.session_id
                row.sender_id = payload.get("sender_id") or row.sender_id
                row.data = payload

            db.add(row)
        db.commit()
    finally:
        db.close()


def load_user_map() -> Dict[str, Dict]:
    session = SessionLocal()
    try:
        rows = session.query(ChatUserMap).all()
        items = []
        for row in rows:
            payload = dict(row.data or {})
            payload.update(
                {
                    "id": row.id,
                    "internal_user_id": row.internal_user_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
            )
            items.append(payload)
    finally:
        session.close()

    out: Dict[str, Dict] = {}
    for item in items:
        internal_id = item.get("internal_user_id")
        if internal_id:
            out[internal_id] = item
    return out


def save_user_map(user_map: Dict[str, Dict]) -> None:
    db = SessionLocal()
    try:
        for internal_id, item in user_map.items():
            payload = dict(item)
            payload["id"] = internal_id
            payload["internal_user_id"] = internal_id

            row = db.get(ChatUserMap, internal_id)
            if not row:
                row = ChatUserMap(
                    id=internal_id,
                    internal_user_id=internal_id,
                    data=payload,
                )
            else:
                row.internal_user_id = internal_id
                row.data = payload

            db.add(row)
        db.commit()
    finally:
        db.close()


def find_user(user_id: str) -> Optional[Dict]:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            return None

        payload = dict(user.metadata_json or {})
        payload.update(
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "password": user.password,
                "supplier_number": user.supplier_number,
                "phone": user.phone,
                "address": user.address,
                "site": user.site,
                "supplier_msid": user.supplier_msid,
                "pinned_rows": user.pinned_rows or [],
                "line_pinned_rows": user.line_pinned_rows or [],
            }
        )
        return payload
    finally:
        session.close()


def find_po(po_id: str) -> Optional[Dict]:
    return find_relational_purchase_order(po_id)


def list_users(role: Optional[str] = None) -> List[Dict]:
    session = SessionLocal()
    try:
        query = session.query(User).filter(User.role != "SUPPLIER")
        if role:
            query = query.filter(User.role == role)
        rows = query.all()
        out = []
        for row in rows:
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
            out.append(payload)
        return out
    finally:
        session.close()


def list_suppliers() -> List[Dict]:
    session = SessionLocal()
    try:
        rows = session.query(User).filter(User.role == "SUPPLIER").all()
        out = []
        for row in rows:
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
            out.append(payload)
        return out
    finally:
        session.close()


def list_purchase_orders() -> List[Dict]:
    return query_relational_purchase_orders()


def participants_signature(participant_ids: List[str]) -> str:
    return "|".join(sorted(set(participant_ids)))


def find_existing_session(
    sessions: List[Dict],
    chat_type: str,
    participant_ids: List[str],
    po_id: Optional[str],
) -> Optional[Dict]:
    expected_signature = participants_signature(participant_ids)

    for session in sessions:
        if session.get("chat_type") != chat_type:
            continue
        if session.get("status") != "ACTIVE":
            continue

        if (session.get("po_id") or "") != (po_id or ""):
            continue

        existing_signature = participants_signature(
            [participant.get("user_id") for participant in session.get("participants", [])]
        )

        if existing_signature == expected_signature:
            return session

    return None


def create_session_record(
    chat_type: str,
    po_id: Optional[str],
    po_number: Optional[str],
    participants: List[Dict],
    created_by: str,
    acs_thread_id: str,
    provider: str,
) -> Dict:
    timestamp = now_iso()

    return {
        "id": str(uuid.uuid4()),
        "chat_type": chat_type,
        "po_id": po_id,
        "po_number": po_number,
        "participants": participants,
        "participants_signature": participants_signature([p.get("user_id") for p in participants]),
        "created_by": created_by,
        "acs_thread_id": acs_thread_id,
        "acs_provider": provider,
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_message_at": None,
        "last_message_preview": "",
        "unread_count_by_user": {participant.get("user_id"): 0 for participant in participants},
        "status": "ACTIVE",
    }


def add_message_record(
    messages: List[Dict],
    session_id: str,
    acs_message_id: str,
    sender_id: str,
    sender_name: str,
    content: str,
    provider: str,
) -> Dict:
    entry = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "acs_message_id": acs_message_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "content": content,
        "provider": provider,
        "created_at": now_iso(),
    }

    messages.append(entry)
    return entry


def filter_user_sessions(
    sessions: List[Dict],
    user_id: str,
    chat_type: Optional[str] = None,
    po_id: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict]:
    filtered = []
    query = (search or "").strip().lower()

    for session in sessions:
        participant_ids = [p.get("user_id") for p in session.get("participants", [])]
        if user_id not in participant_ids:
            continue

        if chat_type and session.get("chat_type") != chat_type:
            continue

        if po_id and session.get("po_id") != po_id:
            continue

        if query:
            haystacks = [
                session.get("po_number") or "",
                session.get("last_message_preview") or "",
            ]

            for participant in session.get("participants", []):
                haystacks.append(participant.get("name") or "")
                haystacks.append(participant.get("user_id") or "")

            if not any(query in text.lower() for text in haystacks):
                continue

        filtered.append(session)

    filtered.sort(key=lambda item: item.get("last_message_at") or item.get("updated_at") or "", reverse=True)
    return filtered


def paginate(items: List[Dict], page: int, page_size: int) -> Tuple[int, List[Dict]]:
    total = len(items)
    start = max((page - 1) * page_size, 0)
    end = start + page_size
    return total, items[start:end]
