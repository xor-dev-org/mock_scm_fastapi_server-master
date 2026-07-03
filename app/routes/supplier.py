from fastapi import APIRouter
from sqlalchemy import select

from app.db.models import User
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.get("")
async def get_suppliers():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.role == "SUPPLIER"))
        rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "email": row.email,
            "role": row.role,
            "password": row.password,
            "supplier_number": row.supplier_number,
            "phone": row.phone,
            "address": row.address,
            "site": row.site,
            "supplier_msid": row.supplier_msid,
            "pinned_rows": row.pinned_rows or [],
            "line_pinned_rows": row.line_pinned_rows or [],
            **(row.metadata_json or {}),
        }
        for row in rows
    ]
