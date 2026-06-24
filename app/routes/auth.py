from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.utils.postgres_db import find_one, insert_one
from app.utils.auth import create_token
import uuid

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

@router.post("/msal/login")
def msal_login(request: MsalLoginRequest):
    user = find_one("users", {"email": request.email})

    if not user or user.get("role") not in ["ADMIN", "PROCUREMENT_SPECIALIST"]:
        raise HTTPException(status_code=401, detail="Invalid user")

    token = create_token(user)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "user": user
    }

@router.post("/supplier/signup")
def supplier_signup(request: SupplierSignupRequest):
    existing = find_one("suppliers", {"email": request.email})

    if existing:
        raise HTTPException(status_code=400, detail="Supplier already exists")

    supplier = {
        "id": str(uuid.uuid4()),
        "supplier_number": request.supplier_number,
        "name": request.name,
        "email": request.email,
        "password": request.password,
        "address": request.address,
        "site": request.site,
        "role": "SUPPLIER"
    }

    inserted = insert_one("suppliers", supplier)
    return inserted

@router.post("/supplier/login")
def supplier_login(request: SupplierLoginRequest):
    supplier = find_one("suppliers", {"email": request.email, "password": request.password})


    if not supplier:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(supplier)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": supplier["role"],
        "user": supplier
    }