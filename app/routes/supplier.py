from fastapi import APIRouter

from app.db.models import User
from app.db.session import SessionLocal

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.get("")
def get_suppliers():
    session = SessionLocal()
    try:
        rows = session.query(User).filter(User.role == "SUPPLIER").all()
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
    finally:
        session.close()