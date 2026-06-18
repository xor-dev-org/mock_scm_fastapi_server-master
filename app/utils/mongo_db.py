import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ServerSelectionTimeoutError

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "scm_procurement")

_client: Optional[MongoClient] = None
_db = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_database():
    global _db
    if _db is None:
        _db = get_client()[MONGO_DB]
    return _db


def get_collection(name: str) -> Collection:
    return get_database()[name]


def _normalize_filter(filter_value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not filter_value:
        return {}
    normalized: Dict[str, Any] = {}
    for key, value in filter_value.items():
        if key == "id":
            normalized["_id"] = value
        else:
            normalized[key] = value
    return normalized


def _clean_document(document: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if document is None:
        return None
    result = dict(document)
    result.pop("_id", None)
    return result


def query_items(collection_name: str, filter_value: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    collection = get_collection(collection_name)
    normalized = _normalize_filter(filter_value)
    results = collection.find(normalized)
    return [_clean_document(item) for item in results]


def find_one(collection_name: str, filter_value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    collection = get_collection(collection_name)
    normalized = _normalize_filter(filter_value)
    return _clean_document(collection.find_one(normalized))


def find_many(collection_name: str, filter_value: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return query_items(collection_name, filter_value)


def insert_one(collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
    collection = get_collection(collection_name)
    payload = dict(document)
    if "id" in payload:
        payload["_id"] = payload["id"]
    else:
        payload["_id"] = str(uuid.uuid4())
        payload["id"] = payload["_id"]
    collection.insert_one(payload)
    return _clean_document(payload)


def replace_one(collection_name: str, filter_value: Dict[str, Any], document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    collection = get_collection(collection_name)
    normalized = _normalize_filter(filter_value)
    payload = dict(document)
    if "id" in payload:
        payload["_id"] = payload["id"]
    elif "_id" in payload:
        payload["id"] = payload["_id"]
    else:
        replacement_id = normalized.get("_id")
        if replacement_id is None:
            replacement_id = str(uuid.uuid4())
            payload["id"] = replacement_id
            payload["_id"] = replacement_id
    collection.replace_one(normalized, payload, upsert=False)
    return _clean_document(payload)


def upsert_one(collection_name: str, filter_value: Dict[str, Any], document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    collection = get_collection(collection_name)
    normalized = _normalize_filter(filter_value)
    payload = dict(document)
    if "id" in payload:
        payload["_id"] = payload["id"]
    elif "_id" in payload:
        payload["id"] = payload["_id"]
    else:
        upsert_id = normalized.get("_id") or str(uuid.uuid4())
        payload["id"] = upsert_id
        payload["_id"] = upsert_id
    collection.replace_one(normalized, payload, upsert=True)
    return _clean_document(payload)


def update_one(collection_name: str, filter_value: Dict[str, Any], update_value: Dict[str, Any]) -> int:
    collection = get_collection(collection_name)
    normalized = _normalize_filter(filter_value)
    result = collection.update_one(normalized, {"$set": update_value})
    return result.modified_count


def delete_one(collection_name: str, filter_value: Dict[str, Any]) -> int:
    collection = get_collection(collection_name)
    normalized = _normalize_filter(filter_value)
    result = collection.delete_one(normalized)
    return result.deleted_count


def count_documents(collection_name: str, filter_value: Optional[Dict[str, Any]] = None) -> int:
    collection = get_collection(collection_name)
    normalized = _normalize_filter(filter_value)
    return collection.count_documents(normalized)


def seed_collection(collection_name: str, file_name: str) -> None:
    file_path = DATA_DIR / file_name
    if not file_path.exists():
        return

    collection = get_collection(collection_name)
    if collection.count_documents({}) > 0:
        return

    with open(file_path, "r", encoding="utf-8") as input_file:
        data = json.load(input_file)

    if isinstance(data, list):
        raw_documents = data
    elif isinstance(data, dict):
        raw_documents = [data]
    else:
        return

    documents: List[Dict[str, Any]] = []
    for document in raw_documents:
        payload = dict(document)
        if "id" in payload:
            payload["_id"] = payload["id"]
        else:
            payload["id"] = str(uuid.uuid4())
            payload["_id"] = payload["id"]
        documents.append(payload)

    if documents:
        collection.insert_many(documents)


def initialize_database() -> None:
    try:
        get_client().admin.command("ping")
    except ServerSelectionTimeoutError as exc:
        raise RuntimeError(
            f"Unable to connect to MongoDB at {MONGO_URI}. Ensure local MongoDB is running."
        ) from exc

    default_mappings = {
        "users": "users.json",
        "suppliers": "suppliers.json",
        "purchase_orders": "purchase_orders.json",
        "delegations": "delegations.json",
    }

    for collection_name, file_name in default_mappings.items():
        seed_collection(collection_name, file_name)

    # Seed other files if they are present but not part of the main application models.
    for file_path in DATA_DIR.glob("*.json"):
        collection_name = file_path.stem
        if collection_name not in default_mappings:
            seed_collection(collection_name, file_path.name)
