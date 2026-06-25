import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

@router.get("/", status_code=200, description="Get all POs")
async def get(db: AsyncSession = Depends(get_db)):
