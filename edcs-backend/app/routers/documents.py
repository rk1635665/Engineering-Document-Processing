import re
import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db, SessionLocal
from ..config import UPLOAD_DIR, MAX_UPLOAD_BYTES, ACCEPTED_EXTENSIONS
from .. import models, schemas
from .. import extraction_pipeline as pipeline
from .. import document_router  # table/CAD layout classifier — routes tables to PaddleOCR+LLM instead of the Florence-2 pipeline below
from . import chat  # generate_insight() — one-shot AI summary, shown in its own UI card

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _document_detail(doc: models.Document) -> schemas.DocumentDetailOut:
    """Builds the full document payload the frontend actually needs in one
    call: the base document fields, a browser-servable file URL, and the
    flat extracted-field breakdown (Document Viewer's "Extracted
    Information" table and the Review & Validation page both read
    `extractedFields` straight off this)."""
    detail = schemas.DocumentDetailOut.model_validate(doc)
    detail.file_url = f"/files/{Path(doc.file_path).name}" if doc.file_path else None
    detail.extracted_fields = [
        schemas.ReviewFieldOut.model_validate(f) for f in doc.review_fields
    ]
    return detail


def _review_fields_from_table_json(table_data: dict) -> list:
    """
    Converts document_router.extract_table_json()/extract_table_json_llm()'s
    dynamic output into the same ReviewField shape the Document Viewer /
    Review & Validation pages already render (field_key/label/value/
    confidence) — so a table document shows up in exactly the same
    "Extracted Information" table a nameplate or P&ID does, with zero
    frontend changes needed. One field per cell, keyed and labeled from
    the table's own detected column names — nothing here is specific to
    any one document.
    """
    fields = []

    tables = table_data.get("tables", [])
    multi = len(tables) > 1
    for t_idx, table in enumerate(tables):
        row_confidences = table.get("rowConfidence") or []
        for r_idx, row in enumerate(table.get("rows", [])):
            # If the LLM path gave us a real per-row OCR confidence, use
            # that (converted 0-1 -> 0-100) uniformly for every cell in
            # that row instead of the shape-based guess below — an actual
            # measurement beats a heuristic whenever we have one.
            row_conf = row_confidences[r_idx] if r_idx < len(row_confidences) else None
            for col, val in row.items():
                key_prefix = f"t{t_idx}_" if multi else ""
                col_slug = re.sub(r"\W+", "_", col.lower()).strip("_") or "field"
                field_key = f"{key_prefix}r{r_idx}_{col_slug}"[:60]
                label = f"{col} (Row {r_idx + 1})" if not multi else f"{col} (Table {t_idx + 1}, Row {r_idx + 1})"
                if row_conf is not None:
                    confidence = round(row_conf * 100) if val is not None else min(45, round(row_conf * 100))
                # Confidence isn't a single fixed number: a missing cell is
                # flagged low for review, a clean numeric read scores
                # higher than free-text (OCR is more reliable on digits).
                elif val is None:
                    confidence = 45
                elif isinstance(val, (int, float)):
                    confidence = 82
                else:
                    confidence = 68
                fields.append({
                    "field_key": field_key,
                    "label": label,
                    "value": "" if val is None else str(val),
                    "confidence": confidence,
                })
    return fields


# Human-readable label for each table-path outcome, keyed by
# document_router.extract_table_json_llm()'s own "structuringMethod"
# value — this is what actually appears in the UI, so a document's
# extraction_method always tells you exactly which engine ran.
_TABLE_METHOD_LABELS = {
    "llm": "PaddleOCR + Qwen2.5 (LLM table structuring)",
    "img2table_fallback": "img2table + EasyOCR (table grid detection)",
}
# _FLORENCE_METHOD_LABEL = "Florence-2 OCR (P&ID / Nameplate pipeline)"
_CAD_NAMEPLATE_METHOD_LABEL = "OpenCV + PaddleOCR (P&ID / Nameplate pipeline)"


def _run_extraction(document_id: str):
    """Background task kicked off right after upload. Runs OCR ->
    classification -> attribute extraction and pushes results straight
    into ExtractedPart / ReviewField, the same tables the two documented
    pipeline-integration endpoints (`/parts`, `/review-fields`) write to.
    Uses its own DB session since it runs outside the request's session.

    Table documents (inspection reports, certs, BOQs, ...) get routed to
    document_router's table extractor — a genuinely new capability, since
    the OCR pipeline below was never built to handle multi-row tabular
    data. Everything else (P&ID, Nameplate, General Arrangement,
    dimensioned CAD drawings) falls through to the same Florence-2
    pipeline call as always. Whichever branch actually runs, doc.status
    and doc.extraction_method both get set so it's never ambiguous what
    processed a given document.
    """
    db = SessionLocal()
    try:
        doc = db.get(models.Document, document_id)
        if not doc or not doc.file_path:
            return

        doc.status = "processing"
        db.commit()

        # Table-routing check. Wrapped defensively: if document_router's
        # dependencies (img2table/pymupdf/paddleocr/easyocr) aren't
        # installed, or classification errors out for any reason, we
        # silently fall through to the Florence-2 pipeline below — never
        # breaks the current flow, even on a machine that hasn't
        # installed the new optional deps yet.
        try:
            classification = document_router.classify_layout(doc.file_path)
        except Exception as e:
            # Previously swallowed silently, which made every document
            # look like a Florence-2 fallback with no way to tell why
            # table routing never even ran. Now the real reason (e.g.
            # missing img2table/pymupdf) survives into reviewer_comment
            # if this document does end up going through Florence-2.
            classification = {"type": "unclassified", "confidence": 0.0}
            doc.reviewer_comment = f"Layout classification failed, treated as unclassified: {e}"

        if classification.get("type") == "table" and classification.get("confidence", 0) >= 0.5:
            table_data = None
            try:
                table_data = document_router.extract_table_json_llm(doc.file_path)
            except document_router.RouterUnavailable:
                # PaddleOCR specifically isn't installed -- that doesn't
                # rule out the img2table+EasyOCR path, which has no
                # PaddleOCR dependency at all. Try it before giving up on
                # table extraction entirely.
                try:
                    table_data = document_router.extract_table_json(doc.file_path)
                except document_router.RouterUnavailable as e:
                    doc.reviewer_comment = f"Table extraction unavailable, fell back to OCR pipeline: {e}"
                except Exception as e:
                    doc.reviewer_comment = f"Table extraction error, fell back to OCR pipeline: {e}"
            except Exception as e:
                doc.reviewer_comment = f"Table extraction error, fell back to OCR pipeline: {e}"

            if table_data:
                review_fields = _review_fields_from_table_json(table_data)
                if review_fields:
                    doc.doc_type = "Table Document"
                    doc.extraction_method = _TABLE_METHOD_LABELS.get(
                        table_data.get("structuringMethod"), "img2table + EasyOCR (table grid detection)"
                    )
                    # Qwen already wrote a summary as part of structuring
                    # the table — reuse it directly rather than paying for
                    # a second LLM call for the same purpose.
                    doc.insight = table_data.get("contextualSummary")
                    doc.parts.clear()
                    doc.review_fields.clear()
                    for f in review_fields:
                        doc.review_fields.append(models.ReviewField(**f))
                    if not doc.insight:
                        # img2table fallback path has no LLM-written summary
                        # of its own — generate one now the same way the
                        # Florence-2 path does below.
                        try:
                            doc.insight = chat.generate_insight(doc)
                        except Exception:
                            pass
                    confidences = [f["confidence"] for f in review_fields]
                    doc.status = "review" if min(confidences) < 70 else "completed"
                    db.commit()
                    return
                # No usable rows came back (e.g. a table img2table found
                # but couldn't OCR) -> fall through to the pipeline below
                # instead of leaving the document with an empty result.

        try:
            result = pipeline.run_pipeline(doc.file_path, doc.name)
        except pipeline.PipelineUnavailable as e:
            doc.status = "failed"
            doc.reviewer_comment = str(e)
            db.commit()
            return
        except Exception as e:  # defensive: never leave a doc stuck in "processing"
            doc.status = "failed"
            doc.reviewer_comment = f"Extraction error: {e}"
            db.commit()
            return

        doc.doc_type = result.doc_type
        doc.extraction_method = _CAD_NAMEPLATE_METHOD_LABEL

        doc.parts.clear()
        for p in result.parts:
            doc.parts.append(models.ExtractedPart(**p))

        doc.review_fields.clear()
        for f in result.review_fields:
            doc.review_fields.append(models.ReviewField(**f))

        confidences = [p["confidence"] for p in result.parts] + [f["confidence"] for f in result.review_fields]
        # Anything with a field under 70% (or nothing extracted at all)
        # goes to human review instead of straight to "completed" — the
        # same threshold the ConfidenceBadge/StatusBadge palette uses.
        needs_review = not confidences or min(confidences) < 70
        doc.status = "review" if needs_review else "completed"
        try:
            doc.insight = chat.generate_insight(doc)
        except Exception:
            # Insight generation is a nice-to-have — never let it block
            # or fail an otherwise-successful extraction.
            pass
        db.commit()
    finally:
        db.close()


@router.get("", response_model=List[schemas.DocumentOut])
def list_documents(
    status: Optional[str] = None,
    type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Backs the Dashboard's Recent Documents table and the Documents page."""
    query = db.query(models.Document)
    if status:
        query = query.filter(models.Document.status == status)
    if type:
        query = query.filter(models.Document.doc_type == type)
    if search:
        query = query.filter(models.Document.name.ilike(f"%{search}%"))
    return query.order_by(models.Document.uploaded_at.desc()).all()


@router.get("/{document_id}", response_model=schemas.DocumentDetailOut)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return _document_detail(doc)


@router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    """Backs the download buttons on Dashboard, Documents, and Document
    Viewer — was referenced by the frontend but not previously implemented."""
    doc = db.get(models.Document, document_id)
    if not doc or not doc.file_path or not Path(doc.file_path).exists():
        raise HTTPException(404, "Document file not found")
    return FileResponse(doc.file_path, filename=doc.name)


@router.post("/upload", response_model=schemas.DocumentDetailOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    type: str = Form("Nameplate"),
    revision: str = Form("Rev. 1"),
    db: Session = Depends(get_db),
):
    """
    Matches the Upload Documents page's drop zone. Validates extension +
    100 MB size limit, saves the file to disk, and creates a Document row
    with status="queued". Immediately schedules the real extraction
    pipeline (OCR -> classification -> attribute extraction) as a
    background task, so the queued -> processing -> review/completed
    lifecycle happens automatically instead of waiting on a separate
    process to poll for queued documents.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ACCEPTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported format: {ext or 'unknown'}")

    doc = models.Document(id=models.new_id("doc"), name=file.filename, doc_type=type, revision=revision, status="queued")

    dest_path = UPLOAD_DIR / f"{doc.id}{ext}"
    size = 0
    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(400, "File exceeds 100 MB limit")
            out.write(chunk)

    doc.file_path = str(dest_path)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_extraction, doc.id)

    return _document_detail(doc)


@router.patch("/{document_id}/status", response_model=schemas.DocumentDetailOut)
def update_status(document_id: str, body: schemas.DocumentStatusUpdate, db: Session = Depends(get_db)):
    """
    Integration point: your extraction pipeline calls this to flip a
    document from "queued" -> "processing", and on to "review" /
    "completed" / "failed" once done (or just include `status` directly
    when pushing parts/review-fields — see those endpoints).
    """
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.status = body.status
    db.commit()
    db.refresh(doc)
    return _document_detail(doc)


@router.post("/{document_id}/review", response_model=schemas.DocumentDetailOut)
def submit_review_decision(document_id: str, body: schemas.ReviewDecisionIn, db: Session = Depends(get_db)):
    """
    Backs the Approve / Reject buttons on the Review & Validation page.
    Approved documents move to "completed"; rejected documents move to
    "failed" so they still surface in the existing StatusBadge palette —
    the original `decision` field preserves the distinction if you later
    want to show "Rejected" separately from a genuine pipeline failure.
    """
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if body.status not in ("approved", "rejected"):
        raise HTTPException(400, "status must be 'approved' or 'rejected'")

    doc.decision = body.status
    doc.reviewer_comment = body.comment
    doc.decided_at = models.utcnow()
    doc.status = "completed" if body.status == "approved" else "failed"
    db.commit()
    db.refresh(doc)
    return _document_detail(doc)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.file_path:
        Path(doc.file_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
