from datetime import datetime

from sqlalchemy import ARRAY, BOOLEAN, DATE, FLOAT, JSON, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base

class Chat(Base):
    __tablename__ = "chat"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String)
    token = Column(String)
    participants = Column(ARRAY(String))


class UserCollection(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class SupplierAuth(Base):
    __tablename__ = "suppliers_auth"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_number: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, index=True, unique=True)
    password: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String)
    site: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="SUPPLIER")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# class PurchaseOrderCollection(Base):
#     __tablename__ = "purchase_orders"

#     id: Mapped[str] = mapped_column(String, primary_key=True)
#     po_number: Mapped[str] = mapped_column(String, index=True)
#     status: Mapped[str] = mapped_column(String, index=True)
#     supplier_id: Mapped[str] = mapped_column(String, index=True)
#     procurement_specialist_id: Mapped[str] = mapped_column(String, index=True)
#     delivery_date: Mapped[str] = mapped_column(String, index=True)
#     mrp_need_by_date: Mapped[Date] = mapped_column(Date, nullable=True)
#     data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
#     created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
#     updated_at: Mapped[datetime] = mapped_column(
#         DateTime,
#         default=datetime.utcnow,
#         onupdate=datetime.utcnow,
#     )

# Base.registry.dispose()

class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = {'extend_existing': True}
    
    msid = Column(Integer, primary_key=True)
    supplier_name = Column(String, nullable=False)
    supplier_dba_name = Column(String, nullable=True)
    category_id = Column(Integer, nullable=True)
    category_id2 = Column(Integer, nullable=True)
    slp_id = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state_province = Column(String, nullable=True)
    iso_country_code = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    payment_term = Column(String, nullable=True)
    incoterm = Column(String, nullable=True)
    segmentation = Column(String, nullable=True)
    tatical_approach = Column(String, nullable=True)
    approval_status = Column(String, nullable=True)
    scobc_ack = Column(String, nullable=True)
    slp_nda_ack = Column(String, nullable=True)
    scobc_received = Column(String, nullable=True)
    scobc_understood = Column(String, nullable=True)
    company_size = Column(Integer, nullable=True)
    scobc_accept = Column(String, nullable=True)
    is_parent = Column(BOOLEAN, nullable=True)
    duns_no = Column(String, nullable=True)
    bp_type = Column(String, nullable=True)
    mdg_managed = Column(BOOLEAN, nullable=True)
    bp_block = Column(BOOLEAN, nullable=True)
    posting_block = Column(BOOLEAN, nullable=True)
    po_block = Column(BOOLEAN, nullable=True)
    diversity = Column(String, nullable=True)
    management_model = Column(String, nullable=True)
    assigned_sqe = Column(String, nullable=True)
    supplier_manager = Column(String, nullable=True)
    due_diligence = Column(String, nullable=True)
    is_archived = Column(BOOLEAN, nullable=True) # Fixed spelling typo 'is_archieve'
    supplier_business_focus = Column(String, nullable=True)

    # ORM Relationships
    purchase_orders = relationship("PO", back_populates="supplier")


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = {'extend_existing': True}
    
    location_id = Column(Integer, primary_key=True)
    location_name = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    iso_country_code = Column(String, nullable=False)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state_province = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    operation = Column(String, nullable=True)
    sector = Column(String)
    division = Column(String)
    istp_flag = Column(BOOLEAN)
    location_status = Column(BOOLEAN, default=True) # Fixed camelCase naming 'location_Status'
    location_type = Column(String)
    heritage_name = Column(String)
    operating_model = Column(String)
    platform_management_region = Column(String)
    is_balanced_scorecard = Column(BOOLEAN)
    business_unit = Column(String)
    ru_no = Column(String)
    is_archived = Column(BOOLEAN, default=False) # Fixed spelling typo 'is_archieved'
    custom_bu = Column(String)

    # ORM Relationships
    purchase_orders = relationship("PO", back_populates="location")
    items = relationship("Item", back_populates="location")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = {'extend_existing': True}
    
    item_no = Column(String, primary_key=True)
    location_id = Column(Integer, ForeignKey("locations.location_id")) # Added database constraint
    site_code = Column(String)
    item_lead_time = Column(Integer)
    pattern_no = Column(String, nullable=True)
    material_code = Column(String)
    item_weight = Column(FLOAT, nullable=True)
    item_weight_unit = Column(String, default="KG")
    is_active = Column(BOOLEAN)
    is_safety_stock = Column(BOOLEAN)
    safety_stock_min = Column(Integer, nullable=True)
    safety_stock_max = Column(Integer, nullable=True)
    stock_level = Column(Integer, nullable=True)

    # ORM Relationships
    location = relationship("Location", back_populates="items")
    purchase_orders = relationship("PO", back_populates="item")


class PO(Base):
    __tablename__ = "purchase_orders"
    # Bundle the composite index inside table args so it updates on re-runs
    # Cleanest way to define a composite index on table initialization in 2.0
    __table_args__ = (
        Index("idx_po_no_line_no", "po_no", "poline_no"),
        {"extend_existing": True}
    )
    
    po_id = Column(Integer, primary_key=True)
    period_date = Column(DATE)
    local_supplier_id = Column(Integer, ForeignKey("suppliers.msid")) # Added database constraint
    location_id = Column(Integer, ForeignKey("locations.location_id")) # Added database constraint
    source_erp = Column(String, nullable=False, default="SAP S4")
    po_no = Column(String, nullable=True, index=True)
    poline_no = Column(String, nullable=True)
    po_release_no = Column(Integer, nullable=True) # Removed duplicate definition row
    po_line_revision_no = Column(Integer, nullable=True)
    po_issue_date = Column(DATE)
    po_line_issue_date = Column(DATE)
    po_status = Column(String, nullable=False, default="Open")
    item_no = Column(String, ForeignKey("items.item_no")) # Added database constraint
    item_description = Column(String, nullable=True)
    quantity_ordered = Column(Integer)
    quantity_outstanding = Column(Integer)
    unit_of_measure = Column(String, nullable=True)
    unit_cost = Column(FLOAT, default=0)
    currency_code = Column(String, nullable=False, default="USD")
    mrp_need_by_date = Column(DATE, nullable=True)
    original_promise_date = Column(DATE, nullable=True)
    latest_promise_date = Column(DATE, nullable=True)
    ots_promise_date = Column(DATE, nullable=True)
    item_category_id = Column(String)
    incoterm = Column(String)
    incoterm_named_place = Column(String)
    payment_term = Column(String)
    seals_ord_no = Column(String, nullable=True)
    drawing_no = Column(String, nullable=True)
    drawing_revision = Column(String, nullable=True)
    shipment_mode = Column(String, nullable=True)
    po_line_ack_status = Column(String, nullable=True)
    po_line_ack_date = Column(DATE, nullable=True)
    savings_type = Column(String, nullable=True)
    savings = Column(Integer, nullable=True)
    std_unit_cost = Column(FLOAT, nullable=True)
    erp_extract_date = Column(DATE, nullable=True)
    except_message = Column(String, nullable=True)
    rescheduling_date = Column(DATE, nullable=True)
    po_feedback = Column(String, nullable=True)
    supplier_email = Column(String, nullable=True)
    purchasing_group = Column(String, nullable=True)
    # Not part of the Excel seed; set by the admin PO-assignment workflow.
    procurement_specialist_id = Column(String, nullable=True)

    # ORM Relationships
    supplier = relationship("Supplier", back_populates="purchase_orders", lazy="selectin")
    location = relationship("Location", back_populates="purchase_orders")
    item = relationship("Item", back_populates="purchase_orders", lazy="selectin")

# Composite multi-column index for lookups targeting specific rows of a PO
# Index("idx_po_no_line_no", PO.po_no, PO.poline_no)



class DelegationCollection(Base):
    __tablename__ = "delegations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True)
    delegated_from_id: Mapped[str] = mapped_column(String, index=True)
    delegated_to_id: Mapped[str] = mapped_column(String, index=True)
    po_id: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ChatSessionCollection(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    po_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    chat_type: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ChatMessageCollection(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    sender_id: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ChatUserMapCollection(Base):
    __tablename__ = "chat_user_map"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    internal_user_id: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class PODocument(Base):
    __tablename__ = "po_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    po_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    line_item_id: Mapped[str] = mapped_column(String, index=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String)
    file_size: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING", nullable=False)
    document_tag_to: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ps_comments: Mapped[str] = mapped_column(Text)
    uploaded_by: Mapped[str] = mapped_column(String, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class POStatusHistory(Base):
    __tablename__ = "po_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    line_item_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_role: Mapped[str] = mapped_column(String, nullable=False)
    previous_status: Mapped[str] = mapped_column(String)
    new_status: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(Text)
    move_in_date: Mapped[Date] = mapped_column(Date, nullable=True)
    move_out_date: Mapped[Date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class POLineSplit(Base):
    __tablename__ = "po_line_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    line_item_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    split_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    delivery_date: Mapped[Date] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SupplierMaster(Base):
    __tablename__ = "supplier_master"

    msid: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    supplier_dba_name: Mapped[str] = mapped_column(String)
    category_id: Mapped[str] = mapped_column(String)
    category_id2: Mapped[str] = mapped_column(String)
    slp_id: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    state_province: Mapped[str] = mapped_column(String)
    iso_country_code: Mapped[str] = mapped_column(String)
    postal_code: Mapped[str] = mapped_column(String)
    payment_term: Mapped[str] = mapped_column(String)
    incoterm: Mapped[str] = mapped_column(String)
    approval_status: Mapped[str] = mapped_column(String)
    assigned_sqe: Mapped[str] = mapped_column(String)
    supplier_manager: Mapped[str] = mapped_column(String)
    is_archived: Mapped[bool] = mapped_column()


class LocationMaster(Base):
    __tablename__ = "location"

    location_id: Mapped[str] = mapped_column(String, primary_key=True)
    location_name: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    iso_country_code: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    state_province: Mapped[str] = mapped_column(String)
    postal_code: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String)
    sector: Mapped[str] = mapped_column(String)
    division: Mapped[str] = mapped_column(String)
    is_archived: Mapped[bool] = mapped_column(default=False)
