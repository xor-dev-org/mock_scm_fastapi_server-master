from fastapi import APIRouter
from app.utils.json_db import read_json

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.get("")
def get_suppliers():
    return read_json("suppliers.json")