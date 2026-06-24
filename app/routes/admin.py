from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.database.models import PO, SupplierAuth, UserCollection

router = APIRouter(prefix="/admin", tags=["Admin"])

SUPPLIER_EDITABLE_FIELDS = ("supplier_number", "name", "email", "password", "address", "site", "role")


def _user_to_dict(user: UserCollection) -> dict:
    return {
        **(user.data or {}),
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "name": user.name,
    }


def _supplier_to_dict(supplier: SupplierAuth) -> dict:
    return {
        "id": supplier.id,
        "supplier_number": supplier.supplier_number,
        "name": supplier.name,
        "email": supplier.email,
        "address": supplier.address,
        "site": supplier.site,
        "role": supplier.role,
    }


@router.get("/users")
async def get_users(role: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Get list of users, optionally filtered by role"""
    query = select(UserCollection)
    if role:
        query = query.where(UserCollection.role == role)

    result = await db.execute(query)
    return [_user_to_dict(user) for user in result.scalars().all()]

@router.put("/supplier/{supplier_id}")
async def update_supplier(supplier_id: str, supplier_data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SupplierAuth).where(SupplierAuth.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    for field in SUPPLIER_EDITABLE_FIELDS:
        if field in supplier_data:
            setattr(supplier, field, supplier_data[field])

    await db.commit()
    await db.refresh(supplier)
    return _supplier_to_dict(supplier)

@router.put("/po-assignment/{po_id}")
async def update_po_assignment(po_id: int, assignment_data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PO).where(PO.po_id == po_id))
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    supplier_id = assignment_data.get("supplier_id")
    po.procurement_specialist_id = assignment_data.get("procurement_specialist_id")
    po.local_supplier_id = int(supplier_id) if supplier_id is not None else None

    await db.commit()
    await db.refresh(po)

    return {
        "po_id": po.po_id,
        "procurement_specialist_id": po.procurement_specialist_id,
        "supplier_id": po.local_supplier_id,
    }
