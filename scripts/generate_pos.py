import json
import uuid
import random
from datetime import date, timedelta

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPLIERS_FILE = os.path.join(BASE_DIR, "data", "suppliers.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "purchase_orders.json")
POS_PER_SUPPLIER = 150

STATUS = ["CREATED", "IN_PROGRESS", "APPROVED", "DELIVERED"]
SOURCE = ["SAP", "ORACLE"]
MRP = ["NONE", "SHORTAGE", "DELAY_RISK", "PRICE_ALERT"]

def load_suppliers():
    with open(SUPPLIERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_po(po_index, supplier, ps_index):
    po_number = f"PO-{10001 + po_index}"
    po_id = str(uuid.uuid4())
    source_system = SOURCE[po_index % len(SOURCE)]
    status = STATUS[po_index % len(STATUS)]
    supplier_id = supplier["id"]
    supplier_name = supplier["name"]
    # assign procurement specialist randomly to avoid one-to-one mapping with supplier
    procurement_specialist_id = f"PS-{random.randint(1, 12):03d}"
    currency = "INR"
    total_value = 10000 + ((po_index * 97) % 490000)
    delivery_date = (date(2026, 6, 1) + timedelta(days=po_index % 120)).isoformat()
    payment_terms = "Net 30"
    mrp_exceptions = MRP[po_index % len(MRP)]
    created_date = date(2026, 5, 28).isoformat()

    line_items = [
        {
            "line_number": 1,
            "material_code": f"MAT-{(po_index % 999) + 1:03d}",
            "description": "Industrial Component",
            "quantity": ((po_index * 13) % 100) + 1,
            "unit_price": ((po_index * 37) % 5000) + 100
        }
    ]

    return {
        "id": po_id,
        "po_number": po_number,
        "source_system": source_system,
        "status": status,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "procurement_specialist_id": procurement_specialist_id,
        "delegated_user_id": "",
        "currency": currency,
        "total_value": total_value,
        "delivery_date": delivery_date,
        "payment_terms": payment_terms,
        "mrp_exceptions": mrp_exceptions,
        "created_date": created_date,
        "line_items": line_items
    }


def main():
    suppliers = load_suppliers()
    pos = []
    po_index = 0
    for s_idx, s in enumerate(suppliers):
        for k in range(POS_PER_SUPPLIER):
            pos.append(generate_po(po_index, s, s_idx))
            po_index += 1

    # shuffle so pages contain mixed suppliers and PS assignments
    random.shuffle(pos)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(pos, f, indent=2)

    # print summary
    counts = {}
    for p in pos:
        counts[p["supplier_id"]] = counts.get(p["supplier_id"], 0) + 1
    print(f"Generated {len(pos)} POs")
    for sup in suppliers:
        print(sup["id"], counts.get(sup["id"], 0))

if __name__ == "__main__":
    main()
