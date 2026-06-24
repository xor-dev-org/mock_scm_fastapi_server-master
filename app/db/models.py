from datetime import datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


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


class SupplierCollection(Base):
    __tablename__ = "suppliers"

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


class PurchaseOrderCollection(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    po_number: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    supplier_id: Mapped[str] = mapped_column(String, index=True)
    procurement_specialist_id: Mapped[str] = mapped_column(String, index=True)
    delivery_date: Mapped[str] = mapped_column(String, index=True)
    mrp_need_by_date: Mapped[Date] = mapped_column(Date, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


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


class ItemMaster(Base):
    __tablename__ = "items"

    item_no: Mapped[str] = mapped_column(String, primary_key=True)
    location_id: Mapped[str] = mapped_column(String, ForeignKey("location.location_id"))
    material_code: Mapped[str] = mapped_column(String)
    item_lead_time: Mapped[int] = mapped_column(Integer)
    item_weight: Mapped[float] = mapped_column(Float)
    item_weight_unit: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column()
    is_safety_stock: Mapped[bool] = mapped_column()
    safety_stock_min: Mapped[int] = mapped_column(Integer)
    safety_stock_max: Mapped[int] = mapped_column(Integer)
