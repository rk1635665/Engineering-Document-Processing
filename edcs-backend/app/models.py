import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """
    One row per uploaded drawing / nameplate. `status` drives the
    StatusBadge everywhere in the UI:
      queued -> processing -> review -> completed
                                    \\-> failed

    Expected flow for your extraction pipeline:
      1. POST /api/documents/upload lands a file here with status="queued".
      2. Your pipeline picks it up (poll GET /api/documents?status=queued,
         or watch the uploads/ folder directly), then PATCHes status to
         "processing".
      3. When done, POST the results to:
           /api/documents/{id}/parts          (detected parts/tags — can
                                                be more than one per doc,
                                                e.g. several P&ID tags)
           /api/documents/{id}/review-fields  (flat field/value/confidence
                                                breakdown for human review,
                                                e.g. a nameplate's fields)
         Either call can also flip status to "review" or "completed" via
         its optional `status` field.
    """

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: new_id("doc"))
    name = Column(String, nullable=False)
    doc_type = Column(String, nullable=False, default="Nameplate")
    revision = Column(String, nullable=False, default="Rev. 1")
    status = Column(String, nullable=False, default="queued")
    uploaded_at = Column(DateTime, default=utcnow)
    file_path = Column(String, nullable=True)
    page_count = Column(Integer, default=1)

    # Populated once a human reviews the extraction (Review & Validation page)
    reviewer_comment = Column(Text, nullable=True)
    decision = Column(String, nullable=True)  # "approved" | "rejected" | None
    decided_at = Column(DateTime, nullable=True)

    # Which OCR/model pipeline actually processed this document, e.g.
    # "PaddleOCR + Qwen2.5 (LLM structuring)" or "Florence-2 OCR
    # (P&ID/Nameplate pipeline)" — set at the end of _run_extraction()
    # in routers/documents.py, whichever branch actually ran. Shown on
    # the Document Viewer's context panel so it's never a mystery which
    # engine produced a given result.
    extraction_method = Column(String, nullable=True)

    # Short AI-generated summary of what this document actually is and
    # what stands out in its extracted data (grounded on doc.parts /
    # doc.review_fields via chat.py's generate_insight()) — shown in its
    # own "AI Insight" card on the Document Viewer, distinct from the
    # flat field-by-field extraction table.
    insight = Column(Text, nullable=True)

    parts = relationship(
        "ExtractedPart", back_populates="document", cascade="all, delete-orphan"
    )
    review_fields = relationship(
        "ReviewField", back_populates="document", cascade="all, delete-orphan"
    )

    @property
    def confidence(self):
        """Overall per-document confidence — average across every
        extracted part/field. Used for the Documents page confidence
        column. Not a stored column; computed on read."""
        values = [p.confidence for p in self.parts] + [f.confidence for f in self.review_fields]
        return round(sum(values) / len(values)) if values else None


class ExtractedPart(Base):
    """
    One detected part/instrument-tag within a document. A single P&ID
    drawing can produce many of these; a nameplate photo usually
    produces exactly one. This is what powers the Extracted Data page
    (one table row per part).
    """

    __tablename__ = "extracted_parts"

    id = Column(String, primary_key=True, default=lambda: new_id("part"))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    part_number = Column(String, nullable=False)
    material = Column(String, nullable=False, default="")
    dimensions = Column(String, nullable=False, default="")
    tolerance = Column(String, nullable=False, default="")
    confidence = Column(Integer, nullable=False, default=0)
    bbox = Column(String, nullable=True)  # "left,top,width,height" % of image

    document = relationship("Document", back_populates="parts")


class ReviewField(Base):
    """
    One editable field/value pair for a document under human review
    (Review & Validation page), each with its own confidence — e.g. a
    nameplate's Part Number, Manufacturer, Material, Set Pressure, etc.
    `field_key` is a stable machine key your pipeline should use
    consistently (part_number, manufacturer, material, set_pressure,
    orifice_size, tolerance, serial_number, ...); `label` is what's
    displayed.
    """

    __tablename__ = "review_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    field_key = Column(String, nullable=False)
    label = Column(String, nullable=False)
    value = Column(String, nullable=False, default="")
    confidence = Column(Integer, nullable=False, default=0)
    bbox = Column(String, nullable=True)

    document = relationship("Document", back_populates="review_fields")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: new_id("notif"))
    tone = Column(String, nullable=False, default="info")  # success|warning|danger|info
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    read = Column(Boolean, default=False)
