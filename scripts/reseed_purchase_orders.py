import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.utils.mongo_db import get_collection

DATA_FILE = BASE_DIR / "data" / "purchase_orders.json"
BACKUP_FILE = BASE_DIR / "data" / "purchase_orders.backup.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reseed purchase_orders collection from JSON seed file")
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip writing a backup of current purchase_orders documents",
    )
    return parser.parse_args()


def load_seed_data() -> list[dict]:
    with open(DATA_FILE, "r", encoding="utf-8") as input_file:
        raw_data = json.load(input_file)

    if not isinstance(raw_data, list):
        raise RuntimeError("Seed file must contain a JSON array of purchase orders")

    return raw_data


def backup_current_data(collection, skip_backup: bool) -> int:
    current_docs = list(collection.find({}))
    if skip_backup:
        return len(current_docs)

    sanitized_docs = []
    for item in current_docs:
        item_copy = dict(item)
        item_copy.pop("_id", None)
        sanitized_docs.append(item_copy)

    with open(BACKUP_FILE, "w", encoding="utf-8") as output_file:
        json.dump(sanitized_docs, output_file, indent=2)

    return len(current_docs)


def build_documents(seed_data: list[dict]) -> list[dict]:
    documents: list[dict] = []
    for po in seed_data:
        payload = dict(po)
        po_id = payload.get("id")
        if not po_id:
            raise RuntimeError("Each purchase order in seed data must have an id")
        payload["_id"] = po_id
        documents.append(payload)
    return documents


def line_item_stats(seed_data: list[dict]) -> tuple[int, int, int]:
    if not seed_data:
        return (0, 0, 0)
    counts = [len(po.get("line_items", [])) for po in seed_data]
    return (min(counts), max(counts), sum(counts))


def main() -> None:
    args = parse_args()
    collection = get_collection("purchase_orders")

    seed_data = load_seed_data()
    existing_count = backup_current_data(collection, args.skip_backup)
    documents = build_documents(seed_data)

    collection.delete_many({})
    if documents:
        collection.insert_many(documents)

    min_items, max_items, total_items = line_item_stats(seed_data)

    print(f"Existing documents before reseed: {existing_count}")
    if not args.skip_backup:
        print(f"Backup written to: {BACKUP_FILE}")
    print(f"Reseeded documents: {len(documents)}")
    print(f"Line item distribution: min={min_items}, max={max_items}, total={total_items}")


if __name__ == "__main__":
    main()
