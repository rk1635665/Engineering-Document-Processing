from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


def camel(snake: str) -> str:
    head, *tail = snake.split("_")
    return head + "".join(word.capitalize() for word in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=camel, from_attributes=True)


# ---------------------------------------------------------------- Documents

class DocumentOut(CamelModel):
    id: str
    name: str
    type: str = Field(validation_alias="doc_type", serialization_alias="type")
    revision: str
    status: str
    confidence: Optional[int] = None


class DocumentDetailOut(DocumentOut):
    uploaded_at: datetime
    page_count: int
    reviewer_comment: Optional[str] = None
    decision: Optional[str] = None
    file_url: Optional[str] = None
    extraction_method: Optional[str] = None
    # Populated from the document's ReviewField rows — the flat,
    # editable field/value/confidence breakdown the extraction pipeline
    # pushes to /review-fields. Powers the Document Viewer's "Extracted
    # Information" table and the Review & Validation page in one shot.
    extracted_fields: List["ReviewFieldOut"] = []


class DocumentCreateMeta(CamelModel):
    """Optional form fields alongside the uploaded file."""
    type: str = "Nameplate"
    revision: str = "Rev. 1"


class DocumentStatusUpdate(CamelModel):
    status: str  # queued | processing | review | completed | failed


# --------------------------------------------------------- Extracted parts

class ExtractedPartIn(CamelModel):
    """One detected part, as your pipeline would report it."""
    part_number: str
    material: str = ""
    dimensions: str = ""
    tolerance: str = ""
    confidence: int = 0


class ExtractedPartsPush(CamelModel):
    parts: List[ExtractedPartIn]
    status: Optional[str] = None  # optionally flip the document's status too


class ExtractedRowOut(CamelModel):
    """Flattened row for the Extracted Data table — one per detected part."""
    id: str
    part_number: str
    material: str
    revision: str
    dimensions: str
    tolerance: str
    confidence: int
    source_document: str
    document_type: str
    document_id: str


# ----------------------------------------------------------- Review fields

class ReviewFieldOut(CamelModel):
    """One editable field row, as used on the Review & Validation page."""
    id: int
    label: str
    value: str
    confidence: int


class ReviewFieldIn(CamelModel):
    field_key: str
    label: str
    value: str
    confidence: int = 0


class ReviewFieldsPush(CamelModel):
    fields: List[ReviewFieldIn]
    status: Optional[str] = None


class ReviewFieldUpdate(CamelModel):
    """A human editing a value in the UI."""
    value: str


# --------------------------------------------------------------- Dashboard

class TrendOut(CamelModel):
    direction: str  # "up" | "down"
    value: str
    period: str


class StatCardOut(CamelModel):
    id: str
    label: str
    value: str
    trend: TrendOut
    tone: Optional[str] = None


# ------------------------------------------------------------------ Review

class ReviewDecisionIn(CamelModel):
    status: str  # "approved" | "rejected"
    comment: Optional[str] = None


# ------------------------------------------------------------- Compare/Diff

class BoundingBoxOut(CamelModel):
    top: str
    left: str
    width: str
    height: str

class DiffRowOut(CamelModel):
    id: str
    attribute: str
    revision_a: str
    revision_b: str
    revision_c: Optional[str] = None
    status: str
    bounding_box_a: Optional[BoundingBoxOut] = None
    bounding_box_b: Optional[BoundingBoxOut] = None
    bounding_box_c: Optional[BoundingBoxOut] = None


class HighlightRegionOut(CamelModel):
    id: str
    x: float
    y: float
    w: float
    h: float
    type: str
    label: str


class CompareResultOut(CamelModel):
    revision_a: str
    revision_b: str
    revision_c: Optional[str] = None
    differences: List[DiffRowOut]
    highlights_a: List[HighlightRegionOut]
    highlights_b: List[HighlightRegionOut]
    insights: Optional[str] = None


# ------------------------------------------------------------- Notifications

class NotificationOut(CamelModel):
    id: str
    tone: str
    title: str
    message: str
    created_at: datetime
    read: bool


# ------------------------------------------------------------------- Chat

class ChatMessageIn(CamelModel):
    """One turn from the AI Chat panel (Document Viewer / Review &
    Validation / Compare Revisions). `history` is optional — the server
    is stateless and always re-grounds on the document's current
    extracted JSON rather than trusting client-replayed context."""
    message: str


class ChatReplyOut(CamelModel):
    reply: str


# DocumentDetailOut.extracted_fields references ReviewFieldOut, which is
# defined later in this file — resolve the forward reference now that
# both classes exist.
DocumentDetailOut.model_rebuild()
