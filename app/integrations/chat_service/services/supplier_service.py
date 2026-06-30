from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from dto.procurement_specialist import SupplierCreate
from database.db import Supplier, supplier_collection


async def create_supplier(supplier: SupplierCreate) -> Supplier:
    """Creates a new supplier in the database."""
    
    try:
        result = await supplier_collection.insert_one({
            "email": supplier.email,
            "name": supplier.name,
            "supplier_code": supplier.supplier_code,
            "organization_name": supplier.organization_name,
            "address": supplier.address,
            "city": supplier.city,
            "state": supplier.state,
            "pincode": supplier.pincode,
            "country": supplier.country
        })
        return Supplier(id=str(result.inserted_id), **supplier.dict())
    except DuplicateKeyError:
        raise HTTPException(
            status_code=400,
            detail="Supplier already exists"
        )