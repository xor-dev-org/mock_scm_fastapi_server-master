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

MRP_EXCEPTION_TYPES = ["SHORTAGE", "DELAY_RISK", "PRICE_ALERT"]
MRP_EXCEPTION_RATE = 0.35

MATERIAL_PREFIX = ["IND", "MCH", "ELC", "HYD", "PMP", "VAL"]

LINE_ITEM_DESCRIPTIONS = [
    "Industrial Component",
    "Hydraulic Assembly",
    "Power Control Unit",
    "Bearing Kit",
    "Sealing Set",
    "Machined Bracket",
]

RECOMMENDATIONS = [
    "MOVE IN",
    "MOVE OUT",
    "QTY CHANGE",
    "MOVE IN & REDUCE",
    "MOVE OUT & INCREASE",
]

RANDOM_SEED = int(os.getenv("PO_SEED", "1806"))
RNG = random.Random(RANDOM_SEED)


def _apply_mrp_recommendation(quantity, required_date):
    """
    Applies MRP recommendation in a data-consistent way.

    MOVE IN              => revised date earlier than need-by date
    MOVE OUT             => revised date later than need-by date
    QTY CHANGE           => updated quantity different from original quantity
    MOVE IN & REDUCE     => revised date earlier + quantity reduced
    MOVE OUT & INCREASE  => revised date later + quantity increased
    """
    recommendation = RNG.choice(RECOMMENDATIONS)

    updated_quantity = None
    updated_delivery_date = None

    required_dt = date.fromisoformat(required_date)

    if recommendation == "MOVE IN":
        updated_delivery_date = (
            required_dt - timedelta(days=RNG.randint(2, 10))
        ).isoformat()

    elif recommendation == "MOVE OUT":
        updated_delivery_date = (
            required_dt + timedelta(days=RNG.randint(2, 15))
        ).isoformat()

    elif recommendation == "QTY CHANGE":
        updated_quantity = max(1, quantity + RNG.choice([-5, -3, 3, 5, 8]))

    elif recommendation == "MOVE IN & REDUCE":
        updated_delivery_date = (
            required_dt - timedelta(days=RNG.randint(2, 10))
        ).isoformat()
        updated_quantity = max(1, quantity - RNG.randint(1, min(quantity, 10)))

    elif recommendation == "MOVE OUT & INCREASE":
        updated_delivery_date = (
            required_dt + timedelta(days=RNG.randint(2, 15))
        ).isoformat()
        updated_quantity = quantity + RNG.randint(1, 10)

    return recommendation, updated_quantity, updated_delivery_date


def _generate_line_item(po_index, line_number, po_status, mrp_exceptions):
    base = (po_index * 17) + (line_number * 13)

    quantity = (base % 120) + 1
    unit_price = ((base * 37) % 4900) + 100

    shipment_date = (
        date(2026, 6, 1) + timedelta(days=(base % 120))
    ).isoformat()

    required_date = (
        date.fromisoformat(shipment_date) + timedelta(days=RNG.randint(1, 20))
    ).isoformat()

    # Temporary rule: line status follows PO status
    status = po_status

    line_id = str(line_number).zfill(5)
    material_prefix = MATERIAL_PREFIX[(base + 3) % len(MATERIAL_PREFIX)]
    net_value = round(quantity * unit_price, 2)

    # Default optional PO review fields
    updated_quantity = None
    updated_unit_price = None
    updated_net_value = None
    updated_delivery_date = None
    supplier_confirmation_date = ""
    concession = ""

    # Default MRP fields
    recommendation = ""
    exception_type = ""
    mrp_action_required = False

    # Scenario decides which PO-review optional fields get values.
    # Not every line should be changed.
    scenario_roll = RNG.random()

    # 40% normal line - no updates
    if scenario_roll < 0.40:
        pass

    # 20% quantity update
    elif scenario_roll < 0.60:
        updated_quantity = max(1, quantity + RNG.randint(-5, 10))
        updated_net_value = round(updated_quantity * unit_price, 2)
        supplier_confirmation_date = (
            date.fromisoformat(shipment_date) + timedelta(days=RNG.randint(1, 8))
        ).isoformat()

    # 15% price update
    elif scenario_roll < 0.75:
        updated_unit_price = max(1, unit_price + RNG.randint(-100, 250))
        updated_net_value = round(quantity * updated_unit_price, 2)
        supplier_confirmation_date = (
            date.fromisoformat(shipment_date) + timedelta(days=RNG.randint(1, 8))
        ).isoformat()

    # 15% delivery date update
    elif scenario_roll < 0.90:
        updated_delivery_date = (
            date.fromisoformat(required_date) + timedelta(days=RNG.randint(2, 15))
        ).isoformat()
        supplier_confirmation_date = (
            date.fromisoformat(shipment_date) + timedelta(days=RNG.randint(1, 8))
        ).isoformat()

    # 10% concession/update-heavy case
    else:
        updated_quantity = max(1, quantity + RNG.randint(-10, 15))
        updated_unit_price = max(1, unit_price + RNG.randint(-150, 300))
        updated_net_value = round(updated_quantity * updated_unit_price, 2)
        updated_delivery_date = (
            date.fromisoformat(required_date) + timedelta(days=RNG.randint(3, 20))
        ).isoformat()
        supplier_confirmation_date = (
            date.fromisoformat(shipment_date) + timedelta(days=RNG.randint(1, 10))
        ).isoformat()
        concession = RNG.choice(["Yes", "No"])

    # MRP fields should appear only when parent PO has MRP exception.
    # Also not every line inside an MRP PO needs recommendation.
    if mrp_exceptions != "NONE":
        exception_type = mrp_exceptions

        if RNG.random() < 0.75:
            recommendation, mrp_updated_quantity, mrp_updated_delivery_date = (
                _apply_mrp_recommendation(quantity, required_date)
            )

            mrp_action_required = True

            if mrp_updated_quantity is not None:
                updated_quantity = mrp_updated_quantity

            if mrp_updated_delivery_date is not None:
                updated_delivery_date = mrp_updated_delivery_date

            if updated_quantity is not None:
                effective_price = (
                    updated_unit_price
                    if updated_unit_price is not None
                    else unit_price
                )
                updated_net_value = round(updated_quantity * effective_price, 2)

            if not supplier_confirmation_date:
                supplier_confirmation_date = (
                    date.fromisoformat(shipment_date)
                    + timedelta(days=RNG.randint(1, 8))
                ).isoformat()

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
        "net_value": net_value,

        # Optional PO review fields
        "updated_quantity": updated_quantity,
        "updated_unit_price": updated_unit_price,
        "updated_net_value": updated_net_value,
        "updated_delivery_date": updated_delivery_date,
        "supplier_confirmation_date": supplier_confirmation_date,
        "concession": concession,

        # Optional MRP fields
        "recommendation": recommendation,
        "exception_type": exception_type,
        "mrp_action_required": mrp_action_required,

        # Temporary: use PO status as line status
        "line_status": status,

        "default_expanded": line_number <= 2,
        "documents": [],
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

    # Assign procurement specialist randomly to avoid one-to-one mapping with supplier
    procurement_specialist_id = f"PS-{RNG.randint(1, 12):03d}"

    currency = "USD"

    delivery_date = (
        date(2026, 6, 1) + timedelta(days=po_index % 120)
    ).isoformat()

    payment_terms = "Net 30"

    # Around 35% POs should have MRP exceptions
    mrp_exceptions = (
        RNG.choice(MRP_EXCEPTION_TYPES)
        if RNG.random() < MRP_EXCEPTION_RATE
        else "NONE"
    )

    created_date = date(2026, 5, 28).isoformat()
    revision_changes = RNG.randint(0, 5)

    line_item_count = RNG.randint(1, 5)

    line_items = [
        _generate_line_item(
            po_index=po_index,
            line_number=line_number,
            po_status=status,
            mrp_exceptions=mrp_exceptions,
        )
        for line_number in range(1, line_item_count + 1)
    ]

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
        "line_items": line_items,
    }


def main():
    suppliers = load_suppliers()
    pos = []
    po_index = 0

    for s_idx, supplier in enumerate(suppliers):
        for _ in range(POS_PER_SUPPLIER):
            pos.append(generate_po(po_index, supplier, s_idx))
            po_index += 1

    # Shuffle so pages contain mixed suppliers and PS assignments
    RNG.shuffle(pos)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(pos, f, indent=2)

    supplier_counts = {}
    status_counts = {}
    mrp_type_counts = {}
    recommendation_counts = {}

    total_line_items = 0
    mrp_po_count = 0
    mrp_line_count = 0

    for po in pos:
        supplier_counts[po["supplier_id"]] = supplier_counts.get(po["supplier_id"], 0) + 1
        status_counts[po["status"]] = status_counts.get(po["status"], 0) + 1
        mrp_type_counts[po["mrp_exceptions"]] = mrp_type_counts.get(po["mrp_exceptions"], 0) + 1

        if po["mrp_exceptions"] != "NONE":
            mrp_po_count += 1

        for item in po["line_items"]:
            total_line_items += 1

            if item.get("mrp_action_required"):
                mrp_line_count += 1

            recommendation = item.get("recommendation") or "NONE"
            recommendation_counts[recommendation] = recommendation_counts.get(recommendation, 0) + 1

            print(f"Generated {total_line_items} line items")
            print(f"MRP exception POs: {mrp_po_count} / {len(pos)} "f"({round((mrp_po_count / len(pos)) * 100, 2)}%)")
            print(f"MRP action line items: {mrp_line_count} / {total_line_items} "f"({round((mrp_line_count / total_line_items) * 100, 2)}%)")
            print("\nPO count by supplier:")
            
            print("\nPO count by status:")
            for status, count in sorted(status_counts.items()):
                print(status, count)

            print("\nPO count by MRP type:")
            for mrp_type, count in sorted(mrp_type_counts.items()):
                print(mrp_type, count)

            print("\nLine item recommendation count:")
            for recommendation, count in sorted(recommendation_counts.items()):
                print(recommendation, count)c


if __name__ == "__main__":
    main()



