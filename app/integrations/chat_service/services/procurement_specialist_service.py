from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from dto.procurement_specialist import ProcurementSpecialistCreate
from database.db import procurement_specialist_collection, ProcurementSpecialist


async def create_procurement_specialist(procurement_specialist: ProcurementSpecialistCreate) -> ProcurementSpecialist:
    """Creates a new procurement specialist in the database."""
    
    try:
        result = await procurement_specialist_collection.insert_one({"email": procurement_specialist.email, "name": "Prasad", "site": "default"})
        return ProcurementSpecialist(id=str(result.inserted_id), name="Prasad", site="default", email=procurement_specialist.email)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )
