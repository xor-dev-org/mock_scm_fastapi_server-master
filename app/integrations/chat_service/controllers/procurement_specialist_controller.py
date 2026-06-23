import logging

from fastapi import APIRouter

from app.integrations.chat_service.dto.procurement_specialist import ProcurementSpecialistCreate

router = APIRouter(prefix="/procurement-specialists", tags=["procurement-specialists"])

@router.post("/", status_code=201, description="Add a new procurement specialist")
async def add_specialist(specialist: ProcurementSpecialistCreate):
    logging.info(f"Adding procurement specialist: {specialist}")

    return {"message": "Procurement specialist added successfully", "status": "success"}