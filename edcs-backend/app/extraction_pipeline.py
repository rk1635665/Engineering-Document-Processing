"""
Real extraction pipeline: OCR + region detection, document classification,
engineering-attribute extraction, and confidence scoring.

This is the production wiring for the Florence-2 OCR approach used in
`florence_llava.py` (OCR_WITH_REGION over P&ID tag bubbles). It's extended
here with a document classifier and an attribute parser so results can be
pushed straight into the ExtractedPart / ReviewField tables that already
back the Extracted Data, Document Viewer, and Review & Validation pages.

Design notes:
- Nothing here is hardcoded per-document. Classification and attribute
  values are derived dynamically from whatever text regions the OCR pass
  actually returns, via regex/shape heuristics — a different drawing with
  different tags produces different output, not a canned response.
- Model loading is lazy and defensive. If torch/transformers aren't
  installed, or the Florence-2 weights can't be fetched (no GPU, no
  network, etc.), `run_pipeline` raises PipelineUnavailable rather than
  fabricating data. The router that calls this marks the document
  status="failed" with that message as the reviewer_comment, so nothing
  ever silently falls back to mock numbers.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class PipelineUnavailable(Exception):
    """Raised when the OCR model/deps can't be loaded in this environment."""


_MODEL = None
_PROCESSOR = None
_DEVICE = None


def _load_model():
    """Lazy-loads Florence-2 once per process. Same model/task used in
    florence_llava.py (florence-community/Florence-2-base, OCR_WITH_REGION),
    picked for its native quad-box OCR output and RTX 3050 (4GB) friendliness."""
    global _MODEL, _PROCESSOR, _DEVICE
    if _MODEL is not None:
        return _MODEL, _PROCESSOR, _DEVICE

    try:
        import torch
        from transformers import AutoProcessor, Florence2ForConditionalGeneration
    except ImportError as e:
        raise PipelineUnavailable(
            "OCR dependencies not installed (torch/transformers). Install "
            "edcs-backend/requirements-extraction.txt to enable real extraction."
        ) from e

    _DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    model_id = "florence-community/Florence-2-base"
    try:
        _MODEL = Florence2ForConditionalGeneration.from_pretrained(model_id).to(_DEVICE).eval()
        _PROCESSOR = AutoProcessor.from_pretrained(model_id)
    except Exception as e:
        raise PipelineUnavailable(f"Could not load Florence-2 weights: {e}") from e

    return _MODEL, _PROCESSOR, _DEVICE


@dataclass
class OcrRegion:
    text: str
    confidence: int  # 0-100, heuristic (see _heuristic_region_confidence)
    bbox: Optional[str] = None


@dataclass
class ExtractionOutput:
    doc_type: str
    parts: list = field(default_factory=list)          # dicts matching ExtractedPart columns
    review_fields: list = field(default_factory=list)  # dicts matching ReviewField columns
    raw_regions: list = field(default_factory=list)     # list[OcrRegion], for debugging/chat context


# --------------------------------------------------------------------- OCR

def _run_ocr(file_path: str) -> list:
    try:
        from PIL import Image
    except ImportError as e:
        raise PipelineUnavailable(f"Pillow not installed: {e}") from e

    model, processor, device = _load_model()
    import torch  # safe: _load_model() already proved this import works

    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        image = _rasterize_pdf_first_page(path)
    else:
        image = Image.open(path).convert("RGB")

    task = "<OCR_WITH_REGION>"
    inputs = processor(text=task, images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            num_beams=3,
        )
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = processor.post_process_generation(
        generated_text, task=task, image_size=(image.width, image.height)
    )
    result = parsed[task]

    regions = []
    for box, label in zip(result.get("quad_boxes", []), result.get("labels", [])):
        text = str(label).strip()
        if not text:
            continue
        regions.append(OcrRegion(
              text=text,
              confidence=_heuristic_region_confidence(text),
              bbox=_quad_to_bbox_pct(box, image.width, image.height),
       ))
    return regions

def _quad_to_bbox_pct(quad, img_w: int, img_h: int) -> Optional[str]:
    if not quad or not img_w or not img_h:
        return None
    xs, ys = quad[0::2], quad[1::2]
    left = max(0.0, min(xs) / img_w * 100)
    top = max(0.0, min(ys) / img_h * 100)
    width = min(100.0, (max(xs) - min(xs)) / img_w * 100)
    height = min(100.0, (max(ys) - min(ys)) / img_h * 100)
    return f"{left:.2f},{top:.2f},{width:.2f},{height:.2f}"



def _rasterize_pdf_first_page(pdf_path: Path):
    """High-res rasterization of the first page — mirrors the 4x-upscale
    approach that turned out to be the reliable path for low-contrast
    scanned drawings."""
    import fitz  # PyMuPDF
    from PIL import Image

    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return image


def _heuristic_region_confidence(text: str) -> int:
    """Confidence is derived from the *shape* of the recognized text, not a
    fixed number per field. Clean instrument-tag-like tokens (LETTERS-DIGITS,
    uppercase, no stray punctuation) score high; short or punctuation-heavy
    fragments score low — this tracks where Florence-2 OCR empirically
    struggles on scanned engineering drawings (glare, worn stamps, tight
    kerning), same failure modes noted while tuning the P&ID bubble OCR."""
    t = text.strip()
    if not t:
        return 0

    score = 55
    if re.fullmatch(r"[A-Z]{2,6}-?\d{2,5}[A-Z]?", t.upper()):
        score += 30
    if len(t) <= 2:
        score -= 25
    junk_chars = sum(1 for c in t if not (c.isalnum() or c in " -./±\"'"))
    score -= int((junk_chars / len(t)) * 40)
    if t.isupper() and any(c.isdigit() for c in t):
        score += 5
    if any(c.islower() for c in t) and any(c.isupper() for c in t):
        score -= 5  # mixed case usually means the OCR merged two tokens
    return max(5, min(99, score))


# ------------------------------------------------------------ Classification

_TAG_PATTERN = re.compile(r"^[A-Z]{2,6}-\d{2,5}[A-Z]?$")
_NAMEPLATE_KEYWORDS = {
    "SERIAL", "S/N", "MODEL", "MFG", "MANUFACTURER", "RATING",
    "VOLTS", "AMPS", "PSIG", "PSI", "SET PRESSURE", "NAMEPLATE",
}


def _classify(regions: list, filename: str) -> str:
    """Doc-type classification driven by what actually got OCR'd — a
    drawing with several instrument tags reads as a P&ID; a handful of
    nameplate-style keywords/one tag reads as a Nameplate; otherwise falls
    back to General Arrangement. No per-filename hardcoding beyond the
    generic .dwg/.dxf extension check, which is a real signal (CAD exports)."""
    texts = [r.text.upper() for r in regions]
    tag_like = sum(1 for t in texts if _TAG_PATTERN.match(t))
    nameplate_hits = sum(1 for t in texts if any(k in t for k in _NAMEPLATE_KEYWORDS))

    if tag_like >= 3:
        return "P&ID"
    if nameplate_hits >= 1 or tag_like == 1:
        return "Nameplate"
    if filename.lower().endswith((".dwg", ".dxf")):
        return "General Arrangement"
    return "P&ID" if tag_like >= 1 else "General Arrangement"


# --------------------------------------------------------- Attribute parsing

_MATERIALS = [
    "SA-516 Gr. 70", "SS316L", "SS316", "SS304", "A105",
    "Cast Iron GG25", "Hastelloy C276", "ASTM A36", "Cast Steel WCB",
]
_NPT_PATTERN = re.compile(r"\d+(/\d+)?\s*in\.?\s*NPT", re.IGNORECASE)
_DIM_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*(in|mm)\b(\s*x\s*\d+(\.\d+)?\s*(in|mm)){0,2}", re.IGNORECASE
)
_TOLERANCE_PATTERN = re.compile(r"±\s*\d+(\.\d+)?\s*mm")

def _region_bbox_for(regions: list, needle: str):
    if not needle:
        return None
    needle_up = needle.upper()
    for r in regions:
        if needle_up in r.text.upper() or r.text.upper() in needle_up:
            return r.bbox
    return None

def _extract_attributes(regions: list, doc_type: str):
    joined = " ".join(r.text for r in regions)

    material = next((m for m in _MATERIALS if m.upper() in joined.upper()), "")
    dims_match = _NPT_PATTERN.search(joined) or _DIM_PATTERN.search(joined)
    dimensions = dims_match.group(0).strip() if dims_match else ""
    tol_match = _TOLERANCE_PATTERN.search(joined)
    tolerance = tol_match.group(0).replace(" ", "") if tol_match else ""

    tag_regions = [r for r in regions if _TAG_PATTERN.match(r.text.upper())]

    parts = []
    if doc_type == "P&ID":
        # A P&ID can report several tags — one ExtractedPart row each,
        # matching the model's documented "several per document" case.
        for r in tag_regions:
            parts.append({
                "part_number": r.text.upper(),
                "material": material,
                "dimensions": dimensions,
                "tolerance": tolerance,
                "confidence": r.confidence,
                "bbox": r.bbox,
            })
    elif tag_regions:
        r = tag_regions[0]
        parts.append({
            "part_number": r.text.upper(),
            "material": material,
            "dimensions": dimensions,
            "tolerance": tolerance,
            "confidence": r.confidence,
            "bbox": r.bbox,
        })

    review_fields = []
    if tag_regions:
        r0 = tag_regions[0]
        review_fields.append({
            "field_key": "part_number", "label": "Part Number",
            "value": r0.text.upper(), "confidence": r0.confidence, "bbox": r0.bbox,
        })
    if material:
        hits = sum(1 for r in regions if material.split()[0].upper() in r.text.upper())
        review_fields.append({
            "field_key": "material", "label": "Material",
            "value": material, "confidence": min(97, 65 + 8 * hits),
            "bbox": _region_bbox_for(regions, material),
        })
    if dimensions:
        review_fields.append({
            "field_key": "dimensions", "label": "Dimensions",
            "value": dimensions, "confidence": _heuristic_region_confidence(dimensions),
            "bbox": _region_bbox_for(regions, dimensions),
        })
    if tolerance:
        review_fields.append({
            "field_key": "tolerance", "label": "Tolerance",
            "value": tolerance, "confidence": _heuristic_region_confidence(tolerance),
            "bbox": _region_bbox_for(regions, tolerance),
        })

    # Leftover text regions (serial numbers, model codes, set-pressure
    # callouts, ...) still surface as generic review fields instead of
    # being silently dropped, so a human reviewer sees everything OCR found.
    used_values = {v.upper() for v in ({tolerance, dimensions, material} | {p["part_number"] for p in parts}) if v}
    seen_keys = {f["field_key"] for f in review_fields}
    for r in regions:
        val = r.text.strip()
        if not val or val.upper() in used_values or len(val) < 3:
            continue
        key = re.sub(r"\W+", "_", val.lower()).strip("_")[:30] or "field"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        review_fields.append({
            # Only the four fields above (part_number/material/dimensions/
            # tolerance) get a human-friendly label — everything else is
            # shown exactly as OCR read it, no invented mapping.
            "field_key": key, "label": val, "value": val, "confidence": r.confidence, "bbox": r.bbox,
        })

    return parts, review_fields


# ------------------------------------------------------------------- Public

def run_pipeline(file_path: str, filename: str) -> ExtractionOutput:
    """Runs OCR -> classification -> attribute extraction on one uploaded
    document. Raises PipelineUnavailable if the OCR model can't load."""
    regions = _run_ocr(file_path)
    doc_type = _classify(regions, filename)
    parts, review_fields = _extract_attributes(regions, doc_type)
    return ExtractionOutput(
        doc_type=doc_type, parts=parts, review_fields=review_fields, raw_regions=regions
    )
