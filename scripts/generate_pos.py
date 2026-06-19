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
LINE_STATUS = ["IN_PROGRESS", "APPROVED", "CANCELLED", "HOLD", "DELIVERED"]
SOURCE = ["SAP", "ORACLE"]
MRP = ["NONE", "SHORTAGE", "DELAY_RISK", "PRICE_ALERT"]
MATERIAL_PREFIX = ["IND", "MCH", "ELC", "HYD", "PMP", "VAL"]
LINE_ITEM_DESCRIPTIONS = [
    "Industrial Component",
    "Hydraulic Assembly",
    "Power Control Unit",
    "Bearing Kit",
    "Sealing Set",
    "Machined Bracket",
]
RANDOM_SEED = int(os.getenv("PO_SEED", "1806"))
RNG = random.Random(RANDOM_SEED)


def _generate_line_item(po_index, line_number):
    base = (po_index * 17) + (line_number * 13)
    quantity = (base % 120) + 1
    unit_price = ((base * 37) % 4900) + 100
    shipment_date = (date(2026, 6, 1) + timedelta(days=(base % 120))).isoformat()
    required_date = (date.fromisoformat(shipment_date) + timedelta(days=RNG.randint(1, 20))).isoformat()
    status = LINE_STATUS[(base + line_number) % len(LINE_STATUS)]
    line_id = str(line_number).zfill(5)
    material_prefix = MATERIAL_PREFIX[(base + 3) % len(MATERIAL_PREFIX)]

    history = [
        {
            "action": status,
            "actor_id": "SYSTEM",
            "actor_role": "SYSTEM",
            "line_item_id": line_id,
            "previous_status": "CREATED",
            "new_status": status,
            "notes": "Seed scenario",
            "timestamp": date(2026, 5, 28).isoformat(),
        }
    ]

    return {
        "id": line_id,
        "line_number": line_number,
        "material_code": f"{material_prefix}-MAT-{(base % 999) + 1:03d}",
        "description": LINE_ITEM_DESCRIPTIONS[base % len(LINE_ITEM_DESCRIPTIONS)],
        "quantity": quantity,
        "unit_price": unit_price,
        "unit": "EA",
        "per": 1,
        "supplier_mat_code": f"SUP-{(base % 700) + 1:03d}",
        "transportation": "PARCEL-GROUND B",
        "shipment_date": shipment_date,
        "required_in_house_date": required_date,
        "net_value": round(quantity * unit_price, 2),
        "line_status": status,
        "default_expanded": line_number <= 2,
        "history": history,
    }

def load_suppliers():
    with open(SUPPLIERS_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def generate_po(po_index, supplier, ps_index):
    po_number = f"PO-{10001 + po_index}"
    po_id = str(uuid.uuid4())
    source_system = SOURCE[po_index % len(SOURCE)]
    status = STATUS[po_index % len(STATUS)]
    supplier_id = supplier["id"]
    supplier_name = supplier["name"]
    supplier_email = supplier["email"]
    site = supplier["site"]
    # assign procurement specialist randomly to avoid one-to-one mapping with supplier
    procurement_specialist_id = f"PS-{random.randint(1, 12):03d}"
    currency = "USD"
    total_value = 10000 + ((po_index * 97) % 490000)
    delivery_date = (date(2026, 6, 1) + timedelta(days=po_index % 120)).isoformat()
    payment_terms = "Net 30"
    mrp_exceptions = MRP[po_index % len(MRP)]
    created_date = date(2026, 5, 28).isoformat()
    revision_changes = random.randint(0,5)

    line_item_count = RNG.randint(1, 5)
    line_items = [_generate_line_item(po_index, line_number) for line_number in range(1, line_item_count + 1)]
    total_value = round(sum(item["net_value"] for item in line_items), 2)

    return {
        "id": po_id,
        "po_number": po_number,
        "source_system": source_system,
        "status": status,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "supplier_email": supplier_email,
        "site": site,
        "procurement_specialist_id": procurement_specialist_id,
        "delegated_user_id": "",
        "currency": currency,
        "total_value": total_value,
        "delivery_date": delivery_date,
        "payment_terms": payment_terms,
        "mrp_exceptions": mrp_exceptions,
        "created_date": created_date,
        "revision_changes": revision_changes,
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
    RNG.shuffle(pos)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(pos, f, indent=2)

    # print summary
    counts = {}
    for p in pos:
        counts[p["supplier_id"]] = counts.get(p["supplier_id"], 0) + 1
    print(f"Generated {len(pos)} POs using seed={RANDOM_SEED}")
    for sup in suppliers:
        print(sup["id"], counts.get(sup["id"], 0))

if __name__ == "__main__":
    main()
