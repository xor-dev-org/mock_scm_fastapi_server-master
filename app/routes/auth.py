import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.database.models import SupplierAuth, UserCollection
from app.utils.auth import create_token

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


@router.post("/msal/login")
async def msal_login(request: MsalLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserCollection).where(UserCollection.email == request.email))
    user = result.scalar_one_or_none()

    if not user or user.role not in ["ADMIN", "PROCUREMENT_SPECIALIST"]:
        raise HTTPException(status_code=401, detail="Invalid user")

    user_dict = _user_to_dict(user)
    token = create_token(user_dict)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user": user_dict,
    }

@router.post("/supplier/signup")
async def supplier_signup(request: SupplierSignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SupplierAuth).where(SupplierAuth.email == request.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Supplier already exists")

    supplier = SupplierAuth(
        id=str(uuid.uuid4()),
        supplier_number=request.supplier_number,
        name=request.name,
        email=request.email,
        password=request.password,
        address=request.address,
        site=request.site,
        role="SUPPLIER",
    )

    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)

    return _supplier_to_dict(supplier)

@router.post("/supplier/login")
async def supplier_login(request: SupplierLoginRequest, db: AsyncSession = Depends(get_db)):
    query = select(SupplierAuth).where(
        SupplierAuth.email == request.email,
        SupplierAuth.password == request.password,
    )
    result = await db.execute(query)
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    supplier_dict = _supplier_to_dict(supplier)
    token = create_token(supplier_dict)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": supplier.role,
        "user": supplier_dict,
    }
