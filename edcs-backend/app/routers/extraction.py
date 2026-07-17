import csv
import io
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api", tags=["extraction"])


def _confidence_bucket(value: int) -> str:
    if value >= 90:
        return "high"
    if value >= 70:
        return "medium"
    return "low"


# --------------------------------------------------------------- Extracted Data page

@router.get("/parts", response_model=List[schemas.ExtractedRowOut])
def list_extracted_parts(
    search: Optional[str] = None,
    confidence: Optional[str] = None,  # all | high | medium | low
    revision: Optional[str] = None,
    document_type: Optional[str] = Query(default=None, alias="documentType"),
    db: Session = Depends(get_db),
):
    """Backs the Extracted Data page's searchable/filterable table."""
    query = db.query(models.ExtractedPart).join(models.Document)

    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.ExtractedPart.part_number.ilike(like))
            | (models.ExtractedPart.material.ilike(like))
            | (models.Document.name.ilike(like))
        )
    if revision and revision != "all":
        query = query.filter(models.Document.revision == revision)
    if document_type and document_type != "all":
        query = query.filter(models.Document.doc_type == document_type)

    rows = query.all()

    if confidence and confidence != "all":
        rows = [r for r in rows if _confidence_bucket(r.confidence) == confidence]

    return [
        schemas.ExtractedRowOut(
            id=r.id,
            part_number=r.part_number,
            material=r.material,
            revision=r.document.revision,
            dimensions=r.dimensions,
            tolerance=r.tolerance,
            confidence=r.confidence,
            source_document=r.document.name,
            document_type=r.document.doc_type,
            document_id=r.document_id,
        )
        for r in rows
    ]


@router.get("/parts/export")
def export_extracted_parts(
    search: Optional[str] = None,
    confidence: Optional[str] = None,
    revision: Optional[str] = None,
    document_type: Optional[str] = Query(default=None, alias="documentType"),
    db: Session = Depends(get_db),
):
    """Backs the Extracted Data page's "Export CSV" button — reuses the
    exact same filtering as the table above so the export always matches
    what's currently on screen."""
    rows = list_extracted_parts(
        search=search, confidence=confidence, revision=revision, document_type=document_type, db=db
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Part Number", "Material", "Revision", "Dimensions", "Tolerance",
        "Confidence", "Source Document", "Document Type",
    ])
    for r in rows:
        writer.writerow([
            r.part_number, r.material, r.revision, r.dimensions, r.tolerance,
            r.confidence, r.source_document, r.document_type,
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=extracted-data.csv"},
    )


@router.get("/documents/{document_id}/parts", response_model=List[schemas.ExtractedRowOut])
def get_document_parts(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return [
        schemas.ExtractedRowOut(
            id=p.id,
            part_number=p.part_number,
            material=p.material,
            revision=doc.revision,
            dimensions=p.dimensions,
            tolerance=p.tolerance,
            confidence=p.confidence,
            source_document=doc.name,
            document_type=doc.doc_type,
            document_id=doc.id,
        )
        for p in doc.parts
    ]


@router.post("/documents/{document_id}/parts", response_model=List[schemas.ExtractedRowOut])
def push_extracted_parts(document_id: str, body: schemas.ExtractedPartsPush, db: Session = Depends(get_db)):
    """
    *** Extraction pipeline integration point #1 ***
    Call this once your CV/OCR pipeline has detected parts/tags in a
    document (a P&ID drawing can report several). Replaces any existing
    parts for this document. Optionally pass `status` to flip the
    document's StatusBadge in the same call (e.g. "review" or "completed").
    """
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.parts.clear()
    for p in body.parts:
        doc.parts.append(
            models.ExtractedPart(
                part_number=p.part_number,
                material=p.material,
                dimensions=p.dimensions,
                tolerance=p.tolerance,
                confidence=p.confidence,
            )
        )
    if body.status:
        doc.status = body.status

    db.commit()
    db.refresh(doc)
    return get_document_parts(document_id, db)


# ----------------------------------------------------------- Review & Validation page

@router.get("/documents/{document_id}/review-fields", response_model=List[schemas.ReviewFieldOut])
def get_review_fields(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc.review_fields


@router.post("/documents/{document_id}/review-fields", response_model=List[schemas.ReviewFieldOut])
def push_review_fields(document_id: str, body: schemas.ReviewFieldsPush, db: Session = Depends(get_db)):
    """
    *** Extraction pipeline integration point #2 ***
    Call this with the flat field/value/confidence breakdown for a
    document that needs human review (typically a nameplate's fields:
    Part Number, Manufacturer, Material, Set Pressure, ...). Replaces
    any existing review fields for this document. Optionally pass
    `status` (usually "review") to flip the StatusBadge in the same call.
    """
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.review_fields.clear()
    for f in body.fields:
        doc.review_fields.append(
            models.ReviewField(
                field_key=f.field_key, label=f.label, value=f.value, confidence=f.confidence
            )
        )
    if body.status:
        doc.status = body.status

    db.commit()
    db.refresh(doc)
    return doc.review_fields


@router.put("/documents/{document_id}/review-fields/{field_id}", response_model=schemas.ReviewFieldOut)
def update_review_field(
    document_id: str, field_id: int, body: schemas.ReviewFieldUpdate, db: Session = Depends(get_db)
):
    """A human editing a value inline on the Review & Validation page."""
    field = (
        db.query(models.ReviewField)
        .filter(models.ReviewField.id == field_id, models.ReviewField.document_id == document_id)
        .first()
    )
    if not field:
        raise HTTPException(404, "Field not found")
    field.value = body.value
    db.commit()
    db.refresh(field)
    return field
