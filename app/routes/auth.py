from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.utils.json_db import read_json, write_json
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
    users = read_json("users.json")

    user = next((u for u in users if u["email"] == request.email and u["role"] in ["ADMIN", "PROCUREMENT_SPECIALIST"]), None)

    if not user:
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
    suppliers = read_json("suppliers.json")

    existing = next((s for s in suppliers if s["email"] == request.email), None)

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

    suppliers.append(supplier)

    write_json("suppliers.json", suppliers)

    return supplier

@router.post("/supplier/login")
def supplier_login(request: SupplierLoginRequest):
    suppliers = read_json("suppliers.json")

    supplier = next(
        (
            s for s in suppliers
            if s["email"] == request.email and s["password"] == request.password
        ),
        None
    )

    if not supplier:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(supplier)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": supplier["role"],
        "user": supplier
    }