import logging

from fastapi import APIRouter

from app.integrations.chat_service.dto.procurement_specialist import SupplierCreate

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

@router.post("/", status_code=201, description="Add a new supplier")
async def add_supplier(supplier: SupplierCreate):
    logging.info(f"Adding supplier: {supplier}")

    return {"message": "Supplier added successfully", "status": "success"}