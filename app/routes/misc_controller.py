import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.utils.sample_data_seed import seed_from_excel

router = APIRouter(prefix="/misc", tags=["misc"])

logger = logging.getLogger(__name__)

SAMPLE_DATA_PATH = Path(__file__).resolve().parents[1] / "resources" / "sample_data.xlsx"


@router.get("/seed-sample-data", status_code=status.HTTP_200_OK)
async def seed_sample_data(db: AsyncSession = Depends(get_db)):
    if not SAMPLE_DATA_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Sample data file not found at {SAMPLE_DATA_PATH}",
        )

    try:
        summary = await seed_from_excel(db, str(SAMPLE_DATA_PATH))
    except Exception as exc:
        logger.exception("misc.seed_sample_data failed")
        raise HTTPException(status_code=500, detail=f"Failed to seed sample data: {exc}") from exc

    return {"status": "completed", "summary": summary}