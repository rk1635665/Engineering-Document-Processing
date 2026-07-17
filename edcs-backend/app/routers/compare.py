import concurrent.futures
import json
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api", tags=["compare"])

# Same env var pattern as chat.py — override with OLLAMA_CHAT_MODEL if you
# want compare insights written by a different local model.
OLLAMA_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llava")
# Same hard ceiling as chat.py — /api/compare used to be instant (pure
# Python, no network calls); without this, a slow/stuck Ollama call would
# hang the whole Compare Revisions page waiting on it.
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "25"))


def _run_with_timeout(fn, timeout: float = OLLAMA_TIMEOUT_S):
    """See chat.py's identical function for why this avoids `with
    ThreadPoolExecutor(...) as executor:` — that pattern blocks on exit
    waiting for the worker thread even after timing out, silently
    defeating the timeout."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        result = future.result(timeout=timeout)
        executor.shutdown(wait=False)
        return result
    except concurrent.futures.TimeoutError:
        executor.shutdown(wait=False)
        return None
    except Exception:
        executor.shutdown(wait=False)
        return None


@router.get("/revisions", response_model=List[str])
def list_revisions(db: Session = Depends(get_db)):
    """Distinct revisions currently in the system."""
    rows = db.query(models.Document.revision).distinct().all()
    return sorted({r[0] for r in rows}) or []


def _part_attrs(part: models.ExtractedPart) -> dict:
    return {"material": part.material, "dimensions": part.dimensions, "tolerance": part.tolerance}


def _bbox_out(bbox_str: Optional[str]) -> Optional[schemas.BoundingBoxOut]:
    """Converts the stored "left,top,width,height" percentage string into
    the {top,left,width,height} object shape the frontend overlay expects.
    Returns None for parts/fields extracted before the bbox column
    existed — the frontend just skips drawing a box for those."""
    if not bbox_str:
        return None
    try:
        left, top, width, height = bbox_str.split(",")
    except ValueError:
        return None
    return schemas.BoundingBoxOut(top=f"{top}%", left=f"{left}%", width=f"{width}%", height=f"{height}%")


# Standard ISA-style instrument tag prefixes (per ISA S5.1) — a fixed,
# real notation reference, not invented per-document. Used to add a
# short, accurate explanation next to a recognized tag instead of
# leaving the reader (or the LLM) to guess what "FT-10" means.
_TAG_GLOSSARY = {
    "FT": "Flow Transmitter", "FV": "Flow Valve", "FIC": "Flow Indicating Controller",
    "LT": "Level Transmitter", "LIC": "Level Indicating Controller",
    "PT": "Pressure Transmitter", "PIC": "Pressure Indicating Controller",
    "TT": "Temperature Transmitter", "TIC": "Temperature Indicating Controller",
    "AD": "Analyzer/Detector", "ISA": "Instrument Air Supply",
}


def _describe_document_kind(doc_types: List[str]) -> str:
    """
    Deterministic, no-hallucination-risk description of what these
    documents actually are — computed from doc_type, not guessed by an
    LLM. This is what answers "what is this document about" reliably;
    the LLM is only ever asked to describe the *changes*, never the
    document category itself.
    """
    types = {t for t in doc_types if t}
    if len(types) != 1:
        return "engineering documents"
    t = next(iter(types)).lower()
    if "p&id" in t or "piping" in t:
        return "P&IDs (Piping and Instrumentation Diagrams) — process flow drawings showing equipment, piping, and instrument tags"
    if "nameplate" in t:
        return "equipment nameplates"
    if "table" in t:
        return "tabular records (e.g. reports or certificates)"
    if "arrangement" in t or "cad" in t:
        return "general arrangement / CAD drawings"
    return f"{next(iter(types))} documents"


def _glossary_hint(attribute: str) -> str:
    """Looks up a recognized ISA tag prefix at the start of an attribute
    string and returns a short parenthetical, or "" if nothing matches.
    Pure lookup against a fixed standard — never invents what a specific
    tag's role is beyond the general instrument-type convention."""
    import re
    m = re.match(r"(?:Instrument Tag )?([A-Za-z]{2,4})[- ]?\d", attribute)
    if m and m.group(1).upper() in _TAG_GLOSSARY:
        return f" ({_TAG_GLOSSARY[m.group(1).upper()]})"
    return ""


def _rule_based_compare_summary(names: List[str], doc_types: List[str], differences: List[schemas.DiffRowOut]) -> str:
    """
    Plain-English summary of what changed, built purely from the diff
    rows — no LLM required. Uses document names (not revision labels,
    which are often identical placeholders like "Rev. 1" across every
    upload) and opens with a deterministic description of the document
    type, so "what is this document" is always answered accurately.
    """
    joined_names = " and ".join(names) if len(names) <= 2 else f"{', '.join(names[:-1])}, and {names[-1]}"
    kind = _describe_document_kind(doc_types)
    opening = f"Comparing {joined_names}, {kind}."

    if not differences:
        return f"{opening} No differences were found between them."

    added = [d for d in differences if d.status == "added"]
    removed = [d for d in differences if d.status == "removed"]
    modified = [d for d in differences if d.status == "modified"]

    def describe(items, limit=5):
        labels = [f"{d.attribute}{_glossary_hint(d.attribute)}" for d in items]
        if len(labels) > limit:
            return f"{', '.join(labels[:limit])}, and {len(labels) - limit} more"
        return ", ".join(labels)

    sentences = [opening]
    if added:
        verb = "was" if len(added) == 1 else "were"
        sentences.append(f"{len(added)} item{'s' if len(added) != 1 else ''} {verb} added: {describe(added)}.")
    if removed:
        verb = "was" if len(removed) == 1 else "were"
        sentences.append(f"{len(removed)} item{'s' if len(removed) != 1 else ''} {verb} removed: {describe(removed)}.")
    if modified:
        verb = "was" if len(modified) == 1 else "were"
        # Each modified item shows its own before -> after, so nothing
        # gets conflated with an unrelated added/removed row.
        changes = "; ".join(f"{d.attribute}{_glossary_hint(d.attribute)}: {d.revision_a} → {d.revision_b}" for d in modified[:5])
        more = f" (+{len(modified) - 5} more)" if len(modified) > 5 else ""
        sentences.append(f"{len(modified)} value{'s' if len(modified) != 1 else ''} {verb} changed — {changes}{more}.")

    return " ".join(sentences)


def _ollama_compare_summary(names: List[str], doc_types: List[str], differences: List[schemas.DiffRowOut]) -> Optional[str]:
    """
    Asks a local Ollama model to turn the raw diff rows into a natural
    paragraph. The prompt is deliberately strict about not linking
    unrelated rows into a fabricated narrative (e.g. claiming a removed
    tag "changed into" an unrelated added one) — the previous looser
    prompt produced exactly that kind of hallucination on a small model.
    Returns None (not an exception) if Ollama isn't reachable, so the
    caller always has the rule-based summary to fall back on.
    """
    if not differences:
        return None
    try:
        import ollama
    except ImportError:
        return None

    kind = _describe_document_kind(doc_types)
    diff_payload = [
        {"attribute": d.attribute, "status": d.status, "before": d.revision_a, "after": d.revision_b}
        for d in differences
    ]
    prompt = (
        f"You're comparing {', '.join(names)} — these are {kind}.\n\n"
        f"Detected differences, as JSON (each object is independent and unrelated to the others "
        f"unless they share the exact same \"attribute\" name):\n{json.dumps(diff_payload, indent=2)}\n\n"
        "Write a short (2-4 sentence) plain-English summary for an engineer reviewing this "
        "comparison.\n\n"
        "STRICT RULES:\n"
        "- Treat every object in the list as a separate, unrelated fact. Never claim one item "
        "\"changed into\" or \"became\" a different item unless a single object's own \"before\" and "
        "\"after\" fields show that change — a \"removed\" item and a different \"added\" item are "
        "NOT the same change, do not connect them.\n"
        "- Only describe status \"modified\" items as having a before/after value change.\n"
        "- Don't invent what any specific tag does beyond standard ISA instrument prefixes "
        "(FT=Flow Transmitter, FV=Flow Valve, LT=Level Transmitter, PT=Pressure Transmitter, "
        "TT=Temperature Transmitter) if the prefix matches; otherwise just name it.\n"
        "- Don't invent details not present in the JSON above.\n"
        "Write connected prose, not a bulleted list."
    )
    try:
        response = _run_with_timeout(lambda: ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}]))
        if response is None:
            return None  # timed out or errored — caller falls back to the rule-based summary
        return response["message"]["content"].strip()
    except Exception:
        return None


def _generate_insights(names: List[str], doc_types: List[str], differences: List[schemas.DiffRowOut]) -> str:
    """Human-readable summary of what changed — tries the local LLM first
    for richer prose, falls back to the rule-based sentence (which is
    always accurate, just plainer) if Ollama isn't available."""
    baseline = _rule_based_compare_summary(names, doc_types, differences)
    return _ollama_compare_summary(names, doc_types, differences) or baseline


@router.get("/compare", response_model=schemas.CompareResultOut)
def compare_documents(
    doc_a: str = Query(alias="docA"),
    doc_b: str = Query(alias="docB"),
    doc_c: Optional[str] = Query(default=None, alias="docC"),
    db: Session = Depends(get_db),
):
    """
    Diffs the extracted parts/tags and review fields already stored for
    two (or optionally three) documents, attribute-by-attribute. Each
    row carries a bounding box per revision it applies to, so the
    frontend can draw a boundary on the actual preview image — sourced
    from the same OCR region coordinates the extraction pipeline
    persists (see ExtractedPart.bbox / ReviewField.bbox).
    """
    a = db.get(models.Document, doc_a)
    b = db.get(models.Document, doc_b)
    if not a or not b:
        raise HTTPException(404, "One or both documents were not found")
    c = db.get(models.Document, doc_c) if doc_c else None
    if doc_c and not c:
        raise HTTPException(404, "Revision C document was not found")

    differences: List[schemas.DiffRowOut] = []
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"diff-{counter}"

    # --- Parts / instrument tags: keyed by part_number -----------------
    parts_a = {p.part_number: p for p in a.parts}
    parts_b = {p.part_number: p for p in b.parts}
    parts_c = {p.part_number: p for p in c.parts} if c else {}

    for tag in sorted(set(parts_a) | set(parts_b) | set(parts_c)):
        pa, pb, pc = parts_a.get(tag), parts_b.get(tag), parts_c.get(tag)
        present = [x for x in (pa, pb, pc) if x is not None]
        if len(present) < (3 if c else 2):
            # missing from at least one selected revision -> added/removed
            status = "added" if pa is None else "removed"
            differences.append(schemas.DiffRowOut(
                id=next_id(), attribute=f"Instrument Tag {tag}",
                revision_a=tag if pa else "—",
                revision_b=tag if pb else "—",
                revision_c=(tag if pc else "—") if c else None,
                status=status,
                bounding_box_a=_bbox_out(pa.bbox) if pa else None,
                bounding_box_b=_bbox_out(pb.bbox) if pb else None,
                bounding_box_c=_bbox_out(pc.bbox) if (c and pc) else None,
            ))
            continue
        # present everywhere selected -> check attribute-level changes
        attrs = [_part_attrs(p) for p in present]
        for attr_key, attr_label in (("material", "Material"), ("dimensions", "Dimensions"), ("tolerance", "Tolerance")):
            values = [x[attr_key] for x in attrs]
            if len(set(values)) > 1:
                differences.append(schemas.DiffRowOut(
                    id=next_id(), attribute=f"{tag} {attr_label}",
                    revision_a=getattr(pa, attr_key) or "—",
                    revision_b=getattr(pb, attr_key) or "—",
                    revision_c=(getattr(pc, attr_key) or "—") if c else None,
                    status="modified",
                    bounding_box_a=_bbox_out(pa.bbox), bounding_box_b=_bbox_out(pb.bbox),
                    bounding_box_c=_bbox_out(pc.bbox) if c else None,
                ))

    # --- Review fields: keyed by field_key ------------------------------
    fields_a = {f.field_key: f for f in a.review_fields}
    fields_b = {f.field_key: f for f in b.review_fields}
    fields_c = {f.field_key: f for f in c.review_fields} if c else {}

    for key in sorted(set(fields_a) | set(fields_b) | set(fields_c)):
        fa, fb, fc = fields_a.get(key), fields_b.get(key), fields_c.get(key)
        present = [x for x in (fa, fb, fc) if x is not None]
        label = present[0].label
        if len(present) < (3 if c else 2):
            status = "added" if fa is None else "removed"
            differences.append(schemas.DiffRowOut(
                id=next_id(), attribute=label,
                revision_a=fa.value if fa else "—",
                revision_b=fb.value if fb else "—",
                revision_c=(fc.value if fc else "—") if c else None,
                status=status,
                bounding_box_a=_bbox_out(fa.bbox) if fa else None,
                bounding_box_b=_bbox_out(fb.bbox) if fb else None,
                bounding_box_c=_bbox_out(fc.bbox) if (c and fc) else None,
            ))
            continue
        values = [x.value for x in present]
        if len(set(values)) > 1:
            differences.append(schemas.DiffRowOut(
                id=next_id(), attribute=label,
                revision_a=fa.value, revision_b=fb.value,
                revision_c=fc.value if c else None,
                status="modified",
                bounding_box_a=_bbox_out(fa.bbox), bounding_box_b=_bbox_out(fb.bbox),
                bounding_box_c=_bbox_out(fc.bbox) if c else None,
            ))

    revisions = [a.revision, b.revision] + ([c.revision] if c else [])
    names = [a.name, b.name] + ([c.name] if c else [])
    doc_types = [a.doc_type, b.doc_type] + ([c.doc_type] if c else [])

    return schemas.CompareResultOut(
        revision_a=a.revision,
        revision_b=b.revision,
        revision_c=c.revision if c else None,
        differences=differences,
        highlights_a=[],
        highlights_b=[],
        insights=_generate_insights(names, doc_types, differences),
    )
