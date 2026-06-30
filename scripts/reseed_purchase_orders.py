import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.models import PurchaseOrderLine
from app.db.session import SessionLocal
from app.utils.postgres_db import create_relational_purchase_order, query_relational_purchase_orders

DATA_FILE = BASE_DIR / "data" / "purchase_orders.json"
BACKUP_FILE = BASE_DIR / "data" / "purchase_orders.backup.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reseed purchase orders in PostgreSQL from JSON seed file")
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


def backup_current_data(skip_backup: bool) -> int:
    current_docs = query_relational_purchase_orders()
    if skip_backup:
        return len(current_docs)

    with open(BACKUP_FILE, "w", encoding="utf-8") as output_file:
        json.dump(current_docs, output_file, indent=2)

    return len(current_docs)


def validate_seed_data(seed_data: list[dict]) -> None:
    for po in seed_data:
        po_id = po.get("id")
        if not po_id:
            raise RuntimeError("Each purchase order in seed data must have an id")


def reseed_purchase_orders(seed_data: list[dict]) -> int:
    session = SessionLocal()
    try:
        session.query(PurchaseOrderLine).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    inserted = 0
    for po in seed_data:
        create_relational_purchase_order(po)
        inserted += 1

    return inserted


def line_item_stats(seed_data: list[dict]) -> tuple[int, int, int]:
    if not seed_data:
        return (0, 0, 0)
    counts = [len(po.get("line_items", [])) for po in seed_data]
    return (min(counts), max(counts), sum(counts))


def main() -> None:
    args = parse_args()
    seed_data = load_seed_data()
    validate_seed_data(seed_data)
    existing_count = backup_current_data(args.skip_backup)
    inserted_count = reseed_purchase_orders(seed_data)

    min_items, max_items, total_items = line_item_stats(seed_data)

    print(f"Existing documents before reseed: {existing_count}")
    if not args.skip_backup:
        print(f"Backup written to: {BACKUP_FILE}")
    print(f"Reseeded documents: {inserted_count}")
    print(f"Line item distribution: min={min_items}, max={max_items}, total={total_items}")


if __name__ == "__main__":
    main()
