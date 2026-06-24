from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.utils.auth import create_token
import uuid

from app.db.models import User
from app.db.session import SessionLocal

router = APIRouter(prefix="/auth", tags=["Auth"])

class MsalLoginRequest(BaseModel):
    email: str

class SupplierSignupRequest(BaseModel):
    supplier_number: str
    name: str
    email: str
    password: str
    address: str
    site: str

class SupplierLoginRequest(BaseModel):
    email: str
    password: str


def _serialize_user(user: User) -> dict:
    payload = dict(user.metadata_json or {})
    payload.update(
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "password": user.password,
            "supplier_number": user.supplier_number,
            "phone": user.phone,
            "address": user.address,
            "site": user.site,
            "supplier_msid": user.supplier_msid,
            "pinned_rows": user.pinned_rows or [],
            "line_pinned_rows": user.line_pinned_rows or [],
        }
    )
    return payload

@router.post("/msal/login")
def msal_login(request: MsalLoginRequest):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email == request.email).first()
    finally:
        session.close()

    if not user or user.role not in ["ADMIN", "PROCUREMENT_SPECIALIST"]:
        raise HTTPException(status_code=401, detail="Invalid user")

    payload = _serialize_user(user)

    token = create_token(payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": payload["role"],
        "user": payload
    }

@router.post("/supplier/signup")
def supplier_signup(request: SupplierSignupRequest):
    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.email == request.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Supplier already exists")

        user = User(
            id=str(uuid.uuid4()),
            supplier_number=request.supplier_number,
            name=request.name,
            email=request.email,
            password=request.password,
            address=request.address,
            site=request.site,
            role="SUPPLIER",
            pinned_rows=[],
            line_pinned_rows=[],
            metadata_json={},
        )

        session.add(user)
        session.commit()
        session.refresh(user)
        return _serialize_user(user)
    finally:
        session.close()

@router.post("/supplier/login")
def supplier_login(request: SupplierLoginRequest):
    session = SessionLocal()
    try:
        supplier = (
            session.query(User)
            .filter(
                User.email == request.email,
                User.password == request.password,
                User.role == "SUPPLIER",
            )
            .first()
        )
    finally:
        session.close()

    if not supplier:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload = _serialize_user(supplier)

    token = create_token(payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": payload["role"],
        "user": payload
    }