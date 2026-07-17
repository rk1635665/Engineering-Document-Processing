import concurrent.futures
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api", tags=["chat"])

# Which local Ollama model answers chat questions. llava works fine on
# text-only prompts (no image passed here); point this at any model name
# already pulled via `ollama pull <name>` — e.g. OLLAMA_CHAT_MODEL=qwen2.5.
OLLAMA_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llava")

# Hard ceiling on any single Ollama call. Without this, a slow/stuck model
# blocks whatever request triggered it indefinitely — the /chat endpoint
# hangs, or (worse) the extraction background task never finishes and a
# document sits in "processing" forever. Override with OLLAMA_TIMEOUT_S
# if your hardware genuinely needs longer.
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "25"))


def _run_with_timeout(fn, timeout: float = OLLAMA_TIMEOUT_S):
    """Runs fn() in a worker thread and gives up after `timeout` seconds,
    returning None instead of hanging. Deliberately does NOT use
    `with ThreadPoolExecutor(...) as executor:` — that context manager
    calls shutdown(wait=True) on exit, which blocks until the worker
    thread finishes regardless of whether we already gave up on it,
    silently defeating the entire point of the timeout. shutdown(wait=False)
    lets this function actually return promptly; the orphaned thread (if
    Ollama truly never responds) is unavoidable in plain Python without
    process-level isolation, but it no longer blocks the caller."""
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


def _build_context(doc: models.Document) -> dict:
    """The exact JSON the AI Chat panel is grounded on — everything the
    pipeline extracted for this document, nothing else."""
    return {
        "name": doc.name,
        "type": doc.doc_type,
        "revision": doc.revision,
        "status": doc.status,
        "parts": [
            {
                "partNumber": p.part_number, "material": p.material,
                "dimensions": p.dimensions, "tolerance": p.tolerance,
                "confidence": p.confidence,
            }
            for p in doc.parts
        ],
        "fields": [
            {"key": f.field_key, "label": f.label, "value": f.value, "confidence": f.confidence}
            for f in doc.review_fields
        ],
    }


def _answer(question: str, context: dict) -> str:
    """
    Rule-based reply generated entirely from `context` (the document's own
    extracted JSON) — no fixed per-document canned text. This is the
    integration point for a real LLM: swap this function's body for a
    call to an OpenAI-compatible chat endpoint (e.g. GLM-5.2) passing
    `context` as grounding/system content and `question` as the user
    turn; everything upstream (the /chat route, the frontend ChatColumn
    wiring) stays the same.
    """
    q = question.lower()

    items = [{"label": f["label"], "value": f["value"], "confidence": f["confidence"]} for f in context["fields"]]
    items += [{"label": f"Part {p['partNumber']}", "value": p["partNumber"], "confidence": p["confidence"]} for p in context["parts"]]

    if not items:
        return (
            f"No extraction results are available yet for {context['name']} "
            f"(status: {context['status']})."
        )

    if any(w in q for w in ["low confidence", "low-confidence", "flagged", "needs review", "review"]):
        low = [i for i in items if i["confidence"] < 70]
        if not low:
            return "Every extracted field is at or above 70% confidence — nothing here needs a second look."
        listed = "; ".join(f"{i['label']} ({i['confidence']}%)" for i in low)
        return f"{len(low)} field(s) are below 70% confidence: {listed}."

    if "material" in q:
        mat = next((i for i in items if i["label"].lower() == "material"), None)
        return f"Material: {mat['value']} ({mat['confidence']}% confidence)." if mat else "No material attribute was extracted for this document."

    if "tolerance" in q:
        tol = next((i for i in items if "tolerance" in i["label"].lower()), None)
        return f"Tolerance: {tol['value']} ({tol['confidence']}% confidence)." if tol else "No tolerance value was extracted."

    if "dimension" in q:
        dim = next((i for i in items if "dimension" in i["label"].lower()), None)
        return f"Dimensions: {dim['value']} ({dim['confidence']}% confidence)." if dim else "No dimensions were extracted."

    if any(w in q for w in ["how many part", "part count", "tags", "instrument"]):
        n = len(context["parts"])
        return f"{n} part(s)/instrument tag(s) were detected in this document." if n else "No discrete parts/instrument tags were detected — this document produced field-level extractions only."

    # Direct field-name lookup, e.g. "what's the serial number?"
    for i in items:
        if i["label"].lower() in q:
            return f"{i['label']}: {i['value']} ({i['confidence']}% confidence)."

    summary = "; ".join(f"{i['label']}: {i['value']} ({i['confidence']}%)" for i in items[:6])
    more = f" (+{len(items) - 6} more)" if len(items) > 6 else ""
    return f"Here's what was extracted from {context['name']}: {summary}{more}."


def _ollama_answer(question: str, context: dict) -> Optional[str]:
    """Calls the local Ollama server (e.g. llava) grounded on this
    document's extracted JSON. Returns None (not an exception) if Ollama
    isn't running or errors, so the caller can fall back cleanly."""
    try:
        import ollama
    except ImportError:
        return None

    system_prompt = (
        "You are an assistant answering questions about one engineering "
        "document's extraction results. Only use the JSON below — don't "
        "invent fields that aren't present. Be concise.\n\n"
        f"Extracted data:\n{json.dumps(context, indent=2)}"
    )
    try:
        response = _run_with_timeout(lambda: ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        ))
        if response is None:
            return None  # timed out or errored — caller falls back cleanly
        return response["message"]["content"].strip()
    except Exception:
        # Ollama not running, model not pulled, connection refused, etc.
        return None


# Same fixed ISA-style instrument tag reference as compare.py — a real
# notation standard, not invented per-document. Kept as a small local
# copy rather than importing from routers/compare.py, since routers stay
# independent of each other in this app (documents.py imports chat.py,
# not the reverse).
_TAG_GLOSSARY = {
    "FT": "Flow Transmitter", "FV": "Flow Valve", "FIC": "Flow Indicating Controller",
    "LT": "Level Transmitter", "LIC": "Level Indicating Controller",
    "PT": "Pressure Transmitter", "PIC": "Pressure Indicating Controller",
    "TT": "Temperature Transmitter", "TIC": "Temperature Indicating Controller",
    "AD": "Analyzer/Detector", "ISA": "Instrument Air Supply",
}


def _glossary_hint(label: str) -> str:
    import re
    m = re.match(r"(?:Part )?([A-Za-z]{2,4})[- ]?\d", label)
    if m and m.group(1).upper() in _TAG_GLOSSARY:
        return f" ({_TAG_GLOSSARY[m.group(1).upper()]})"
    return ""


def _describe_document_kind(doc_type: str) -> str:
    """Deterministic, no-hallucination-risk description of the document
    category — computed from doc_type, not guessed."""
    t = (doc_type or "").lower()
    if "p&id" in t or "piping" in t:
        return "a P&ID (Piping and Instrumentation Diagram) — a process flow drawing showing equipment, piping, and instrument tags"
    if "nameplate" in t:
        return "an equipment nameplate"
    if "table" in t:
        return "a tabular record (e.g. a report or certificate)"
    if "arrangement" in t or "cad" in t:
        return "a general arrangement / CAD drawing"
    return f"a {doc_type or 'document'}"


def _rule_based_insight(context: dict) -> str:
    """
    Human-readable document summary built purely from context — no LLM
    involved. This is what generate_insight() falls back to when Ollama
    isn't running/reachable, so the AI Insight card always has something
    to show instead of silently disappearing whenever the LLM call fails.
    """
    items = [{"label": f["label"], "value": f["value"], "confidence": f["confidence"]} for f in context["fields"]]
    items += [{"label": f"Part {p['partNumber']}", "value": p["partNumber"], "confidence": p["confidence"]} for p in context["parts"]]

    if not items:
        return f"{context['name']} has not produced any extraction results yet (status: {context['status']})."

    kind = _describe_document_kind(context["type"])
    sentences = [f"{context['name']} (revision {context['revision']}) is {kind}, with {len(items)} extracted field(s)."]

    low = [i for i in items if i["confidence"] < 70]
    if low:
        names = ", ".join(f"{i['label']}{_glossary_hint(i['label'])}" for i in low[:5])
        more = f" and {len(low) - 5} more" if len(low) > 5 else ""
        sentences.append(f"{len(low)} field(s) are below 70% confidence and worth a second look: {names}{more}.")
    else:
        sentences.append("Every extracted field is at or above 70% confidence.")

    highlights = [i for i in items if i["label"].lower() in ("material", "part number", "tolerance", "dimensions")]
    if highlights:
        described = "; ".join(f"{i['label']}: {i['value']}" for i in highlights)
        sentences.append(f"Key values — {described}.")

    return " ".join(sentences)


def generate_insight(doc: models.Document) -> Optional[str]:
    """
    One-shot AI summary for a document, called once right after
    extraction finishes (routers/documents.py's _run_extraction) rather
    than per-chat-turn. Reuses _build_context() so it's grounded on
    exactly the same parts/review_fields data the chat panel sees — no
    separate/duplicated extraction logic. Returns None (not an
    exception) if Ollama isn't reachable or has nothing to summarize,
    so callers can just skip setting doc.insight rather than branch on
    a raised error.
    """
    context = _build_context(doc)
    if not context["parts"] and not context["fields"]:
        return None

    kind = _describe_document_kind(context["type"])
    prompt = (
        f"This document is {kind}. Write a short (2-4 sentence) plain-English "
        "insight about it for someone reviewing it. Cover: what stands out in "
        "the extracted values (unusual specs, low-confidence fields worth "
        "double-checking, missing data), and one practical takeaway if there "
        "is one. If a field name matches a standard ISA instrument prefix "
        "(FT=Flow Transmitter, FV=Flow Valve, LT=Level Transmitter, "
        "PT=Pressure Transmitter, TT=Temperature Transmitter), you can mention "
        "that — otherwise don't guess what a tag means. Don't just restate the "
        "JSON as a list — write connected prose. Only use what's actually "
        "present below; don't invent details.\n\n"
        f"{json.dumps(context, indent=2)}"
    )
    return _ollama_answer(prompt, context) or _rule_based_insight(context)


@router.post("/documents/{document_id}/chat", response_model=schemas.ChatReplyOut)
def chat_with_document(document_id: str, body: schemas.ChatMessageIn, db: Session = Depends(get_db)):
    doc = db.get(models.Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    context = _build_context(doc)
    reply = _ollama_answer(body.message, context) or _answer(body.message, context)
    return schemas.ChatReplyOut(reply=reply)
