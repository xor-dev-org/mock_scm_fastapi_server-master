import logging
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Type

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Item, Location, PO, Supplier

logger = logging.getLogger(__name__)


def is_null(val: Any) -> Any:
    if pd.isna(val):
        return None

    if isinstance(val, str):
        val_clean = val.strip()
        if val_clean == "" or val_clean.upper() == "NULL":
            return None

    return val


def set_bool_flag(val: Any) -> Optional[bool]:
    if is_null(val) is None:
        return None

    if isinstance(val, str):
        return val.strip().upper() in ("Y", "YES", "TRUE")

    try:
        return float(val) == 1.0
    except (ValueError, TypeError):
        return False


def _to_str(val: Any) -> Optional[str]:
    val = is_null(val)
    if val is None:
        return None
    return str(val).strip()


def _to_int(val: Any) -> Optional[int]:
    val = is_null(val)
    if val is None:
        return None
    try:
        return int(round(float(val)))
    except (ValueError, TypeError):
        return None


def _to_float(val: Any) -> Optional[float]:
    val = is_null(val)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _to_date(val: Any) -> Optional[date]:
    val = is_null(val)
    if val is None:
        return None
    # pd.Timestamp/datetime are both subclasses of date, so they must be
    # truncated via .date() before the plain-date isinstance check below.
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return pd.Timestamp(val).date()
    except (ValueError, TypeError):
        return None


def _dedupe_by_key(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    deduped: Dict[Any, Dict[str, Any]] = {}
    for row in rows:
        deduped[row[key]] = row
    return list(deduped.values())


def build_supplier_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _, record in df.iterrows():
        msid = _to_int(record.get("MSID"))
        supplier_name = _to_str(record.get("SUPPLIER_NAME"))
        if msid is None or supplier_name is None:
            continue
        rows.append(
            {
                "msid": msid,
                "supplier_name": supplier_name,
                "supplier_dba_name": _to_str(record.get("SUPPLIER_DBA_NAME")),
                "category_id": _to_int(record.get("CATEGORY_ID")),
                "category_id2": _to_int(record.get("CATEGORY_ID2")),
                "slp_id": _to_str(record.get("SLP_ID")),
                "address": _to_str(record.get("ADDRESS_LINE")),
                "city": _to_str(record.get("CITY")),
                "state_province": _to_str(record.get("STATE_PROVINCE")),
                "iso_country_code": _to_str(record.get("ISO_COUNTRY_CD")),
                "postal_code": _to_str(record.get("POSTAL_CD")),
                "payment_term": _to_str(record.get("PAYMENT_TERM")),
                "incoterm": _to_str(record.get("INCOTERM")),
                "segmentation": _to_str(record.get("SEGMENTATION")),
                "tatical_approach": _to_str(record.get("TACTICAL_APPROACH")),
                "approval_status": _to_str(record.get("APPROVAL_STATUS")),
                "scobc_ack": _to_str(record.get("SCOBC_ACKN")),
                "slp_nda_ack": _to_str(record.get("SLP_NDA_ACKN")),
                "scobc_received": _to_str(record.get("SCOBC_RECEIVED")),
                "scobc_understood": _to_str(record.get("SCOBC_UNDERSTOOD")),
                "company_size": _to_int(record.get("COMPANY_SIZE")),
                "scobc_accept": _to_str(record.get("SCOBC_ACCEPT")),
                "is_parent": set_bool_flag(record.get("IS_PARENT")),
                "duns_no": _to_str(record.get("DUNS_NO")),
                "bp_type": _to_str(record.get("BP_TYPE")),
                "mdg_managed": set_bool_flag(record.get("MDG_MANAGED")),
                "bp_block": set_bool_flag(record.get("BP_BLOCK")),
                "posting_block": set_bool_flag(record.get("POSTING_BLOCK")),
                "po_block": set_bool_flag(record.get("PO_BLOCK")),
                "diversity": _to_str(record.get("DIVERSITY")),
                "management_model": _to_str(record.get("MANAGEMENT_MODEL")),
                "assigned_sqe": _to_str(record.get("ASSIGNED_SQE")),
                "supplier_manager": _to_str(record.get("SUPPLIER_MANAGER")),
                "due_diligence": _to_str(record.get("DUE_DILIGENCE")),
                "is_archived": set_bool_flag(record.get("ARCHIVE_FLAG")),
                "supplier_business_focus": _to_str(record.get("SUPPLIER_BUSINESS_FOCUS")),
            }
        )
    return _dedupe_by_key(rows, "msid")


def build_location_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _, record in df.iterrows():
        location_id = _to_int(record.get("LOCATION_ID"))
        location_name = _to_str(record.get("LOCATION_NAME"))
        platform = _to_str(record.get("PLATFORM"))
        iso_country_code = _to_str(record.get("ISO_COUNTRY_CD"))
        if location_id is None or location_name is None or platform is None or iso_country_code is None:
            continue
        rows.append(
            {
                "location_id": location_id,
                "location_name": location_name,
                "platform": platform,
                "iso_country_code": iso_country_code,
                "address": _to_str(record.get("ADDRESS")),
                "city": _to_str(record.get("CITY")),
                "state_province": _to_str(record.get("STATE_PROVINCE")),
                "postal_code": _to_str(record.get("POSTAL_CODE")),
                "operation": _to_str(record.get("OPERATION")),
                "sector": _to_str(record.get("SECTOR")),
                "division": _to_str(record.get("DIVISION")),
                "istp_flag": set_bool_flag(record.get("ISTP_FLG")),
                "location_status": set_bool_flag(record.get("LOCATION_STATUS")),
                "location_type": _to_str(record.get("LOCATION_TYPE")),
                "heritage_name": _to_str(record.get("HERITAGE_NAME")),
                "operating_model": _to_str(record.get("OPERATING_MODEL")),
                "platform_management_region": _to_str(record.get("PLATFORM_MGMT_REGION")),
                "is_balanced_scorecard": set_bool_flag(record.get("BALANCED_SCORECARD_FLG")),
                "business_unit": _to_str(record.get("BUSINESS_UNIT")),
                "ru_no": _to_str(record.get("RU#")),
                "is_archived": set_bool_flag(record.get("ARCHIVE_FLAG")),
                "custom_bu": _to_str(record.get("CUSTOM_BU")),
            }
        )
    return _dedupe_by_key(rows, "location_id")


def build_item_rows(df: pd.DataFrame, valid_location_ids: Optional[set] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _, record in df.iterrows():
        item_no = _to_str(record.get("ITEM_NO"))
        if item_no is None:
            continue
        location_id = _to_int(record.get("LOCATION_ID"))
        if valid_location_ids is not None and location_id not in valid_location_ids:
            location_id = None
        rows.append(
            {
                "item_no": item_no,
                "location_id": location_id,
                "site_code": _to_str(record.get("SITE_CD")),
                "item_lead_time": _to_int(record.get("ITEM_LEADTIME")),
                "pattern_no": _to_str(record.get("PATTERN_NO")),
                "material_code": _to_str(record.get("MATERIAL_CODE")),
                "item_weight": _to_float(record.get("ITEM_WEIGHT")),
                "item_weight_unit": _to_str(record.get("ITEM_WEIGHT_UNIT")),
                "is_active": set_bool_flag(record.get("ACTIVE_FLG")),
                "is_safety_stock": set_bool_flag(record.get("SAFTEY_STOCK")),
                "safety_stock_min": _to_int(record.get("SS_MIN")),
                "safety_stock_max": _to_int(record.get("SS_MAX")),
                "stock_level": _to_int(record.get("STOCK_LEVEL")),
            }
        )
    # ITEM_NO is not unique in the source sheet (same item stocked at multiple
    # locations); the table's PK is item_no alone, so the last occurrence wins.
    return _dedupe_by_key(rows, "item_no")


def build_po_rows(
    df: pd.DataFrame,
    valid_supplier_msids: Optional[set] = None,
    valid_location_ids: Optional[set] = None,
    valid_item_nos: Optional[set] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _, record in df.iterrows():
        po_id = _to_int(record.get("PO_ID"))
        if po_id is None:
            continue

        local_supplier_id = _to_int(record.get("MSID"))
        if valid_supplier_msids is not None and local_supplier_id not in valid_supplier_msids:
            local_supplier_id = None

        location_id = _to_int(record.get("LOCATION_ID"))
        if valid_location_ids is not None and location_id not in valid_location_ids:
            location_id = None

        item_no = _to_str(record.get("ITEM_NO"))
        if valid_item_nos is not None and item_no not in valid_item_nos:
            item_no = None

        rows.append(
            {
                "po_id": po_id,
                "period_date": _to_date(record.get("PERIOD_DT")),
                "local_supplier_id": local_supplier_id,
                "location_id": location_id,
                "source_erp": _to_str(record.get("SOURCE_SYSTEM_CD")) or "SAP S4",
                "po_no": _to_str(record.get("PO_NO")),
                "poline_no": _to_str(record.get("PO_LINE_NO")),
                "po_release_no": _to_int(record.get("PO_RELEASE_NO")),
                "po_line_revision_no": _to_int(record.get("PO_LINE_REVISION_NO")),
                "po_issue_date": _to_date(record.get("PO_ISSUE_DT")),
                "po_line_issue_date": _to_date(record.get("PO_LINE_ISSUE_DT")),
                "po_status": _to_str(record.get("PO_STATUS")) or "Open",
                "item_no": item_no,
                "item_description": _to_str(record.get("ITEM_DESC")),
                "quantity_ordered": _to_int(record.get("QUANTITY_ORD")),
                "quantity_outstanding": _to_int(record.get("QUANTITY_OUTSTANDING")),
                "unit_of_measure": _to_str(record.get("UNIT_OF_MEASURE")),
                "unit_cost": _to_float(record.get("UNIT_COST")),
                "currency_code": _to_str(record.get("CURRENCY")) or "USD",
                "mrp_need_by_date": _to_date(record.get("MRP_NEED_BY_DT")),
                "original_promise_date": _to_date(record.get("ORIGINAL_PROM_DATE")),
                "latest_promise_date": _to_date(record.get("LATEST_PROMISE_DATE")),
                "ots_promise_date": _to_date(record.get("OTS_PROMISE _DATE")),
                "item_category_id": _to_str(record.get("ITEM_CATEGORY_ID")),
                "incoterm": _to_str(record.get("INCOTERM")),
                "incoterm_named_place": _to_str(record.get("INCOTERM_NAMED_PLACE")),
                "payment_term": _to_str(record.get("PAYMENT_TERM")),
                "seals_ord_no": _to_str(record.get("SALES_ORD_NO")),
                "drawing_no": _to_str(record.get("DRAWING_NO")),
                "drawing_revision": _to_str(record.get("DRAWING_REV")),
                "shipment_mode": _to_str(record.get("SHIPMENT_MODE")),
                "po_line_ack_status": _to_str(record.get("PO_LINE_ACKN_STATUS")),
                "po_line_ack_date": _to_date(record.get("PO_LINE_ACKN_DT")),
                "savings_type": _to_str(record.get("SAVINGS_TYPE")),
                "savings": _to_int(record.get("SAVINGS")),
                "std_unit_cost": _to_float(record.get("STD_UNIT_COST")),
                "erp_extract_date": _to_date(record.get("ERP_Extract_Date")),
                "except_message": _to_str(record.get("EXCEPT_MESSAGE")),
                "rescheduling_date": _to_date(record.get("RESCHEDULING_DATE")),
                "po_feedback": _to_str(record.get("PO_FEEDBACK")),
                "supplier_email": _to_str(record.get("SUPPLIER_EMAIL")),
                "purchasing_group": _to_str(record.get("PURCHASING_GROUP")),
            }
        )
    return _dedupe_by_key(rows, "po_id")


ASYNCPG_MAX_QUERY_PARAMS = 32767


async def upsert_rows(
    db: AsyncSession,
    model: Type[Any],
    rows: Sequence[Dict[str, Any]],
    pk_columns: Iterable[str],
) -> int:
    if not rows:
        return 0

    pk_columns = list(pk_columns)
    columns = model.__table__.columns
    update_columns_names = [column.name for column in columns if column.name not in pk_columns]

    # asyncpg rejects statements with more than 32767 bound parameters, so a
    # single VALUES list of thousands of wide rows must be sent in batches.
    batch_size = max(1, ASYNCPG_MAX_QUERY_PARAMS // len(columns))

    for offset in range(0, len(rows), batch_size):
        batch = rows[offset : offset + batch_size]
        stmt = pg_insert(model).values(list(batch))
        update_columns = {name: getattr(stmt.excluded, name) for name in update_columns_names}
        stmt = stmt.on_conflict_do_update(index_elements=pk_columns, set_=update_columns)
        await db.execute(stmt)

    return len(rows)


async def seed_from_excel(db: AsyncSession, excel_path: str) -> Dict[str, Any]:
    sheets = pd.read_excel(
        excel_path,
        sheet_name=["SUPPLIERS", "LOCATION", "ITEMS", "OPENPO"],
    )

    summary: Dict[str, Any] = {}

    supplier_rows = build_supplier_rows(sheets["SUPPLIERS"])
    location_rows = build_location_rows(sheets["LOCATION"])
    valid_location_ids = {row["location_id"] for row in location_rows}
    item_rows = build_item_rows(sheets["ITEMS"], valid_location_ids)
    valid_supplier_msids = {row["msid"] for row in supplier_rows}
    valid_item_nos = {row["item_no"] for row in item_rows}
    po_rows = build_po_rows(
        sheets["OPENPO"],
        valid_supplier_msids=valid_supplier_msids,
        valid_location_ids=valid_location_ids,
        valid_item_nos=valid_item_nos,
    )

    for name, model, rows, pk_columns in (
        ("suppliers", Supplier, supplier_rows, ["msid"]),
        ("locations", Location, location_rows, ["location_id"]),
        ("items", Item, item_rows, ["item_no"]),
        ("purchase_orders", PO, po_rows, ["po_id"]),
    ):
        try:
            seeded = await upsert_rows(db, model, rows, pk_columns)
            await db.commit()
            summary[name] = {"seeded": seeded}
        except Exception as exc:
            await db.rollback()
            logger.exception("sample_data_seed.%s_failed", name)
            summary[name] = {"error": str(exc)}

    return summary
