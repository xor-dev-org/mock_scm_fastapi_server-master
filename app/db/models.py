from datetime import datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SupplierMaster(Base):
    __tablename__ = "suppliers"

    msid: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    supplier_dba_name: Mapped[str | None] = mapped_column(String, nullable=True)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_id2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slp_id: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state_province: Mapped[str | None] = mapped_column(String, nullable=True)
    iso_country_code: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_term: Mapped[str | None] = mapped_column(String, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String, nullable=True)
    segmentation: Mapped[str | None] = mapped_column(String, nullable=True)
    tactical_approach: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_status: Mapped[str | None] = mapped_column(String, nullable=True)
    scobc_ack: Mapped[str | None] = mapped_column(String, nullable=True)
    slp_nda_ack: Mapped[str | None] = mapped_column(String, nullable=True)
    scobc_received: Mapped[str | None] = mapped_column(String, nullable=True)
    scobc_understood: Mapped[str | None] = mapped_column(String, nullable=True)
    company_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scobc_accept: Mapped[str | None] = mapped_column(String, nullable=True)
    is_parent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duns_no: Mapped[str | None] = mapped_column(String, nullable=True)
    bp_type: Mapped[str | None] = mapped_column(String, nullable=True)
    mdg_managed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bp_block: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    posting_block: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    po_block: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    diversity: Mapped[str | None] = mapped_column(String, nullable=True)
    management_model: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_sqe: Mapped[str | None] = mapped_column(String, nullable=True)
    supplier_manager: Mapped[str | None] = mapped_column(String, nullable=True)
    due_diligence: Mapped[str | None] = mapped_column(String, nullable=True)
    is_archived: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    supplier_business_focus: Mapped[str | None] = mapped_column(String, nullable=True)


class LocationMaster(Base):
    __tablename__ = "locations"

    location_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_name: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    iso_country_code: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state_province: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    operation: Mapped[str | None] = mapped_column(String, nullable=True)
    sector: Mapped[str] = mapped_column(String, nullable=False, default="")
    division: Mapped[str] = mapped_column(String, nullable=False, default="")
    istp_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    location_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    location_type: Mapped[str] = mapped_column(String, nullable=False, default="")
    heritage_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    operating_model: Mapped[str] = mapped_column(String, nullable=False, default="")
    platform_management_region: Mapped[str] = mapped_column(String, nullable=False, default="")
    is_balanced_scorecard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    business_unit: Mapped[str] = mapped_column(String, nullable=False, default="")
    ru_no: Mapped[str] = mapped_column(String, nullable=False, default="")
    is_archived: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    custom_bu: Mapped[str] = mapped_column(String, nullable=False, default="")


class ItemMaster(Base):
    __tablename__ = "items"
    __table_args__ = (Index("idx_items_location_item", "location_id", "item_no"),)

    item_no: Mapped[str] = mapped_column(String, primary_key=True)
    location_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        nullable=False,
    )
    site_code: Mapped[str | None] = mapped_column(String, nullable=True)
    item_lead_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pattern_no: Mapped[str | None] = mapped_column(String, nullable=True)
    material_code: Mapped[str] = mapped_column(String, nullable=False)
    item_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    item_weight_unit: Mapped[str | None] = mapped_column(String, nullable=True, default="KG")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_safety_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    safety_stock_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safety_stock_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_level: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("idx_po_no_line_no", "po_no", "poline_no"),
        Index("idx_po_header_id", "po_header_id"),
    )

    po_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_header_id: Mapped[str] = mapped_column(String, nullable=False)
    period_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    local_supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("suppliers.msid", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_erp: Mapped[str] = mapped_column(String, nullable=False, default="SAP S4")
    po_no: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    poline_no: Mapped[str | None] = mapped_column(String, nullable=True)
    po_release_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    po_line_revision_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    po_issue_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    po_line_issue_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    po_status: Mapped[str] = mapped_column(String, nullable=False, default="Open")
    item_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("items.item_no", ondelete="CASCADE"),
        nullable=False,
    )
    item_description: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_outstanding: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_of_measure: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency_code: Mapped[str] = mapped_column(String, nullable=False, default="USD")
    mrp_need_by_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    original_promise_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    latest_promise_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    ots_promise_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    item_category_id: Mapped[str | None] = mapped_column(String, nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String, nullable=True)
    incoterm_named_place: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_term: Mapped[str | None] = mapped_column(String, nullable=True)
    seals_ord_no: Mapped[str | None] = mapped_column(String, nullable=True)
    drawing_no: Mapped[str | None] = mapped_column(String, nullable=True)
    drawing_revision: Mapped[str | None] = mapped_column(String, nullable=True)
    shipment_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    po_line_ack_status: Mapped[str | None] = mapped_column(String, nullable=True)
    po_line_ack_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    savings_type: Mapped[str | None] = mapped_column(String, nullable=True)
    savings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    std_unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    erp_extract_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    except_message: Mapped[str | None] = mapped_column(String, nullable=True)
    rescheduling_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    po_feedback: Mapped[str | None] = mapped_column(String, nullable=True)
    supplier_email: Mapped[str | None] = mapped_column(String, nullable=True)
    purchasing_group: Mapped[str | None] = mapped_column(String, nullable=True)

    # Explicit operational/UI fields; avoid generic row-level blobs.
    procurement_specialist_id: Mapped[str | None] = mapped_column(String, nullable=True)
    delegated_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    line_status: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_delivery_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    updated_material_no: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_description: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_net_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    line_documents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    line_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    split_deliveries: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    concession_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    concession_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    supplier = relationship("SupplierMaster", lazy="joined")
    location = relationship("LocationMaster", lazy="joined")
    item = relationship("ItemMaster", lazy="joined")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String, index=True, nullable=False)
    password: Mapped[str | None] = mapped_column(String, nullable=True)
    supplier_number: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    site: Mapped[str | None] = mapped_column(String, nullable=True)
    supplier_msid: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.msid"), nullable=True)
    pinned_rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    line_pinned_rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    po_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    po_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    supplier_name: Mapped[str | None] = mapped_column(String, nullable=True)
    delegated_from_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    delegated_to_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    total_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    chat_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    po_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    po_number: Mapped[str | None] = mapped_column(String, nullable=True)
    participants: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    participants_signature: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    acs_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    acs_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    unread_count_by_user: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True, default="ACTIVE")
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ChatUserMap(Base):
    __tablename__ = "chat_user_map"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    internal_user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PODocument(Base):
    __tablename__ = "po_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    po_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    line_item_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING", nullable=False)
    document_tag_to: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ps_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class POStatusHistory(Base):
    __tablename__ = "po_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    line_item_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_role: Mapped[str] = mapped_column(String, nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String, nullable=True)
    new_status: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    move_in_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    move_out_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)


class POLineSplit(Base):
    __tablename__ = "po_line_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    line_item_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    split_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)


# Compatibility aliases for existing imports during migration.
UserCollection = User
SupplierCollection = User
PurchaseOrderCollection = PurchaseOrderLine
DelegationCollection = Delegation
ChatSessionCollection = ChatSession
ChatMessageCollection = ChatMessage
ChatUserMapCollection = ChatUserMap
