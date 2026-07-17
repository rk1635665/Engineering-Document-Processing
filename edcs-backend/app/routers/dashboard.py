from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=List[schemas.StatCardOut])
def dashboard_stats(db: Session = Depends(get_db)):
    """
    Backs the four Dashboard stat cards. Values are computed live from
    the database. NOTE: the trend fields (e.g. "+8.2% vs last week")
    are placeholders — computing a real trend needs a historical
    snapshot table, which isn't wired up yet. Swap these once you're
    ready to track day-over-day snapshots.
    """
    total_documents = db.query(func.count(models.Document.id)).scalar() or 0
    total_parts = db.query(func.count(models.ExtractedPart.id)).scalar() or 0
    total_fields = db.query(func.count(models.ReviewField.id)).scalar() or 0
    extracted_fields = total_parts + total_fields

    avg_confidence = db.query(func.avg(models.ExtractedPart.confidence)).scalar()
    if avg_confidence is None:
        avg_confidence = db.query(func.avg(models.ReviewField.confidence)).scalar() or 0
    extraction_accuracy = round(float(avg_confidence), 1)

    pending_reviews = (
        db.query(func.count(models.Document.id))
        .filter(models.Document.status == "review")
        .scalar()
        or 0
    )

    return [
        schemas.StatCardOut(
            id="total-documents",
            label="Total Documents",
            value=f"{total_documents:,}",
            trend=schemas.TrendOut(direction="up", value="—", period="vs last week"),
        ),
        schemas.StatCardOut(
            id="extracted-fields",
            label="Extracted Fields",
            value=f"{extracted_fields:,}",
            trend=schemas.TrendOut(direction="up", value="—", period="vs last week"),
        ),
        schemas.StatCardOut(
            id="extraction-accuracy",
            label="Extraction Accuracy",
            value=f"{extraction_accuracy}%",
            trend=schemas.TrendOut(direction="up", value="—", period="vs last week"),
        ),
        schemas.StatCardOut(
            id="pending-reviews",
            label="Pending Reviews",
            value=str(pending_reviews),
            trend=schemas.TrendOut(direction="down", value="—", period="vs yesterday"),
            tone="warning",
        ),
    ]
