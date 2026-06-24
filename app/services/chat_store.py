import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.utils.postgres_db import find_one, insert_one, query_items, update_one, upsert_one

CHAT_SESSIONS_COLLECTION = os.getenv("CHAT_SESSIONS_COLLECTION", "chat_sessions")
CHAT_MESSAGES_COLLECTION = os.getenv("CHAT_MESSAGES_COLLECTION", "chat_messages")
CHAT_USER_MAP_COLLECTION = os.getenv("CHAT_USER_MAP_COLLECTION", "chat_user_map")
USERS_COLLECTION = os.getenv("USERS_COLLECTION", "users")
SUPPLIERS_COLLECTION = os.getenv("SUPPLIERS_COLLECTION", "suppliers")
PURCHASE_ORDERS_COLLECTION = os.getenv("PURCHASE_ORDERS_COLLECTION", "purchase_orders")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sessions() -> List[Dict]:
    return query_items(CHAT_SESSIONS_COLLECTION, {"doc_type": "chat_session"})


def save_sessions(sessions: List[Dict]) -> None:
    for session in sessions:
        payload = dict(session)
        payload.setdefault("id", str(uuid.uuid4()))
        payload["_id"] = payload["id"]
        payload["doc_type"] = "chat_session"
        payload["partition_key"] = "chat_session"
        upsert_one(CHAT_SESSIONS_COLLECTION, {"id": payload["id"]}, payload)


def load_messages() -> List[Dict]:
    return query_items(CHAT_MESSAGES_COLLECTION, {"doc_type": "chat_message"})


def save_messages(messages: List[Dict]) -> None:
    for message in messages:
        payload = dict(message)
        payload.setdefault("id", str(uuid.uuid4()))
        payload["_id"] = payload["id"]
        payload["doc_type"] = "chat_message"
        payload["partition_key"] = payload.get("session_id", "chat_message")
        upsert_one(CHAT_MESSAGES_COLLECTION, {"id": payload["id"]}, payload)


def load_user_map() -> Dict[str, Dict]:
    items = query_items(CHAT_USER_MAP_COLLECTION, {"doc_type": "chat_user_map"})

    out: Dict[str, Dict] = {}
    for item in items:
        internal_id = item.get("internal_user_id")
        if internal_id:
            out[internal_id] = item
    return out


def save_user_map(user_map: Dict[str, Dict]) -> None:
    for internal_id, item in user_map.items():
        payload = dict(item)
        payload["id"] = internal_id
        payload["_id"] = internal_id
        payload["internal_user_id"] = internal_id
        payload["doc_type"] = "chat_user_map"
        payload["partition_key"] = "chat_user_map"
        upsert_one(CHAT_USER_MAP_COLLECTION, {"id": internal_id}, payload)


def find_user(user_id: str) -> Optional[Dict]:
    user = find_one(USERS_COLLECTION, {"id": user_id})
    if user:
        return user

    supplier = find_one(SUPPLIERS_COLLECTION, {"id": user_id})
    return supplier


def find_po(po_id: str) -> Optional[Dict]:
    return find_one(PURCHASE_ORDERS_COLLECTION, {"id": po_id})


def list_users(role: Optional[str] = None) -> List[Dict]:
    if role:
        return query_items(USERS_COLLECTION, {"role": role})
    return query_items(USERS_COLLECTION)


def list_suppliers() -> List[Dict]:
    return query_items(SUPPLIERS_COLLECTION)


def list_purchase_orders() -> List[Dict]:
    return query_items(PURCHASE_ORDERS_COLLECTION)


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
