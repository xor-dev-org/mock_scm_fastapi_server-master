from fastapi import APIRouter
from app.utils.postgres_db import query_items

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

@router.get("")
def get_suppliers():
    return query_items("suppliers")