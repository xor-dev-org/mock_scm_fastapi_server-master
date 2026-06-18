import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from azure.cosmos import CosmosClient, exceptions

CHAT_SESSIONS_CONTAINER = os.getenv("AZURE_COSMOS_CHAT_SESSIONS_CONTAINER", "chat_sessions")
CHAT_MESSAGES_CONTAINER = os.getenv("AZURE_COSMOS_CHAT_MESSAGES_CONTAINER", "chat_messages")
CHAT_USER_MAP_CONTAINER = os.getenv("AZURE_COSMOS_CHAT_USER_MAP_CONTAINER", "chat_user_map")
USERS_CONTAINER = os.getenv("AZURE_COSMOS_USERS_CONTAINER", "users")
SUPPLIERS_CONTAINER = os.getenv("AZURE_COSMOS_SUPPLIERS_CONTAINER", "suppliers")
PURCHASE_ORDERS_CONTAINER = os.getenv("AZURE_COSMOS_PURCHASE_ORDERS_CONTAINER", "purchase_orders")


class CosmosRepository:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_COSMOS_ENDPOINT", "")
        self.key = os.getenv("AZURE_COSMOS_KEY", "")
        self.database_name = os.getenv("AZURE_COSMOS_DATABASE", "procurement")
        self._client = None
        self._database = None

    def _ensure_database(self):
        if not self.endpoint or not self.key:
            raise RuntimeError(
                "Azure Cosmos DB is not configured. Set AZURE_COSMOS_ENDPOINT and AZURE_COSMOS_KEY."
            )

        if self._database is not None:
            return self._database

        self._client = CosmosClient(self.endpoint, credential=self.key)
        self._database = self._client.create_database_if_not_exists(id=self.database_name)
        return self._database

    def _container(self, container_name: str):
        database = self._ensure_database()
        return database.create_container_if_not_exists(
            id=container_name,
            partition_key={"paths": ["/partition_key"], "kind": "Hash"},
        )

    def query_items(self, container_name: str, query: str, parameters: Optional[List[Dict]] = None) -> List[Dict]:
        container = self._container(container_name)
        try:
            return list(
                container.query_items(
                    query=query,
                    parameters=parameters or [],
                    enable_cross_partition_query=True,
                )
            )
        except exceptions.CosmosHttpResponseError:
            return []

    def upsert_item(self, container_name: str, item: Dict) -> None:
        container = self._container(container_name)
        container.upsert_item(item)


cosmos_repo = CosmosRepository()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sessions() -> List[Dict]:
    return cosmos_repo.query_items(
        CHAT_SESSIONS_CONTAINER,
        "SELECT * FROM c WHERE c.doc_type = @doc_type",
        [{"name": "@doc_type", "value": "chat_session"}],
    )


def save_sessions(sessions: List[Dict]) -> None:
    for session in sessions:
        payload = dict(session)
        payload.setdefault("id", str(uuid.uuid4()))
        payload["doc_type"] = "chat_session"
        payload["partition_key"] = "chat_session"
        cosmos_repo.upsert_item(CHAT_SESSIONS_CONTAINER, payload)


def load_messages() -> List[Dict]:
    return cosmos_repo.query_items(
        CHAT_MESSAGES_CONTAINER,
        "SELECT * FROM c WHERE c.doc_type = @doc_type",
        [{"name": "@doc_type", "value": "chat_message"}],
    )


def save_messages(messages: List[Dict]) -> None:
    for message in messages:
        payload = dict(message)
        payload.setdefault("id", str(uuid.uuid4()))
        payload["doc_type"] = "chat_message"
        payload["partition_key"] = payload.get("session_id", "chat_message")
        cosmos_repo.upsert_item(CHAT_MESSAGES_CONTAINER, payload)


def load_user_map() -> Dict[str, Dict]:
    items = cosmos_repo.query_items(
        CHAT_USER_MAP_CONTAINER,
        "SELECT * FROM c WHERE c.doc_type = @doc_type",
        [{"name": "@doc_type", "value": "chat_user_map"}],
    )

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
        payload["internal_user_id"] = internal_id
        payload["doc_type"] = "chat_user_map"
        payload["partition_key"] = "chat_user_map"
        cosmos_repo.upsert_item(CHAT_USER_MAP_CONTAINER, payload)


def find_user(user_id: str) -> Optional[Dict]:
    query = "SELECT TOP 1 * FROM c WHERE c.id = @id"
    params = [{"name": "@id", "value": user_id}]

    users = cosmos_repo.query_items(USERS_CONTAINER, query, params)
    if users:
        return users[0]

    suppliers = cosmos_repo.query_items(SUPPLIERS_CONTAINER, query, params)
    if suppliers:
        return suppliers[0]

    return None


def find_po(po_id: str) -> Optional[Dict]:
    items = cosmos_repo.query_items(
        PURCHASE_ORDERS_CONTAINER,
        "SELECT TOP 1 * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": po_id}],
    )
    return items[0] if items else None


def list_users(role: Optional[str] = None) -> List[Dict]:
    if role:
        return cosmos_repo.query_items(
            USERS_CONTAINER,
            "SELECT * FROM c WHERE c.role = @role",
            [{"name": "@role", "value": role}],
        )

    return cosmos_repo.query_items(USERS_CONTAINER, "SELECT * FROM c")


def list_suppliers() -> List[Dict]:
    return cosmos_repo.query_items(SUPPLIERS_CONTAINER, "SELECT * FROM c")


def list_purchase_orders() -> List[Dict]:
    return cosmos_repo.query_items(PURCHASE_ORDERS_CONTAINER, "SELECT * FROM c")


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
