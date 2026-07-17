"""
document_router.py — standalone document classification + extraction.

This is a NEW, self-contained module. It does not import, call, or modify
`extraction_pipeline.py` or anything else in the existing app — nothing
about the current P&ID/nameplate pipeline changes as a result of this file
existing.

What it does:
    1. classify_layout()      -- decides whether a page is dominated by a
                                  TABLE grid or by CAD/technical line-art,
                                  for both images and PDFs.
    2. extract_table_json_llm() -- PREFERRED table path: PaddleOCR raw
                                  tokens + confidence, structured into JSON
                                  (with a contextual summary) by a local
                                  LLM via Ollama. Falls back automatically
                                  to (3) if PaddleOCR/Ollama aren't
                                  available.
    3. extract_table_json()   -- FALLBACK table path: img2table (OpenCV
                                  grid detection) + EasyOCR. No LLM needed.
    4. extract_cad_json()     -- OCRs a CAD/drawing page and turns whatever
                                  "LABEL: VALUE" pairs it can find into
                                  JSON, dynamic keys.
    5. infer_json_schema()    -- generates a real JSON Schema (draft-07)
                                  from whatever data came out of 2/3/4, by
                                  introspecting it — never a fixed schema.
    6. process_document()     -- the single entry point: classify, extract
                                  (LLM path first, rule-based fallback),
                                  infer schema, return one JSON-ready dict.

Dependencies:
    Fallback table/CAD path (no LLM, no PaddleOCR):
        pip install img2table[easyocr] pymupdf opencv-python-headless
    Preferred table path (PaddleOCR + local LLM structuring):
        pip install paddleocr paddlepaddle ollama
        + `ollama pull qwen2.5:3b` (or set OLLAMA_STRUCTURE_MODEL)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional


class RouterUnavailable(Exception):
    """Raised when a required optional dependency isn't installed. Callers
    get an honest error instead of a silent/fake result."""


# --------------------------------------------------------------------- types

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
PDF_EXT = {".pdf"}


# ------------------------------------------------------------- classification

def classify_layout(file_path: str) -> dict:
    """
    Decides whether the document is TABLE-dominated or CAD/DRAWING-dominated.

    Returns:
        {
          "type": "table" | "cad_drawing" | "unclassified",
          "confidence": 0-1 float,
          "signals": {...}   # the raw measurements that drove the decision,
                              # kept so the caller/reviewer can see *why*
        }

    Nothing here is a fixed per-document answer — every branch is driven
    by measurements taken from the actual file (vector-path counts, text
    alignment, line density), so a different document produces a
    different classification, not a canned one.
    """
    ext = Path(file_path).suffix.lower()

    if ext in PDF_EXT:
        result = _classify_pdf(file_path)
        if result["type"] != "unclassified":
            return result
        # No usable text/vector layer (scanned PDF) -> fall through to the
        # image-based path on a rasterized first page.
        image = _rasterize_pdf_first_page(file_path)
        return _classify_image(image)

    if ext in IMAGE_EXT:
        from PIL import Image as PILImage
        return _classify_image(PILImage.open(file_path).convert("RGB"))

    return {"type": "unclassified", "confidence": 0.0, "signals": {"reason": f"unsupported extension {ext}"}}


def _classify_pdf(file_path: str) -> dict:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RouterUnavailable(f"pymupdf not installed: {e}") from e

    doc = fitz.open(file_path)
    page = doc[0]

    drawings = page.get_drawings()
    text_blocks = page.get_text("blocks")
    doc.close()

    vector_path_count = len(drawings)
    # A vector path with many points (curves/complex outlines) reads as
    # more "drawing-like" than a handful of straight ruling lines.
    vector_point_count = sum(len(d.get("items", [])) for d in drawings)

    text_only_blocks = [b for b in text_blocks if b[6] == 0]  # type 0 = text
    alignment_score = _text_grid_alignment_score(text_only_blocks)

    signals = {
        "vector_path_count": vector_path_count,
        "vector_point_count": vector_point_count,
        "text_block_count": len(text_only_blocks),
        "text_grid_alignment_score": round(alignment_score, 3),
    }

    # A raw alignment-grid check alone isn't reliable here: CAD drawings
    # commonly have grid-aligned text too (revision history tables,
    # tolerance blocks in the title block). What actually separates a
    # drawing from a table is how much vector line-art there is *per
    # unit of text* — a drawing is mostly lines with sparse annotation
    # text; a table is mostly text with at most a few border rectangles.
    vector_density_per_text = vector_point_count / max(1, len(text_only_blocks))
    signals["vector_density_per_text_block"] = round(vector_density_per_text, 2)

    if vector_density_per_text > 5 and vector_point_count > 40:
        confidence = min(0.95, 0.5 + vector_density_per_text / 40)
        return {"type": "cad_drawing", "confidence": round(confidence, 2), "signals": signals}

    if alignment_score >= 0.35 and len(text_only_blocks) >= 6:
        confidence = min(0.95, 0.4 + alignment_score)
        return {"type": "table", "confidence": round(confidence, 2), "signals": signals}

    return {"type": "unclassified", "confidence": 0.0, "signals": signals}


def _text_grid_alignment_score(blocks: list) -> float:
    """How strongly text-block left-edges and top-edges cluster into a
    repeated row/column grid — the geometric signature of a table.
    0 = scattered prose, 1 = a perfect grid. Computed purely from the
    block coordinates on this page, nothing pre-set."""
    if len(blocks) < 4:
        return 0.0
    xs = [round(b[0], 0) for b in blocks]
    ys = [round(b[1], 0) for b in blocks]

    def repeat_ratio(vals, tolerance=6):
        buckets: list[list[float]] = []
        for v in sorted(vals):
            placed = False
            for bucket in buckets:
                if abs(bucket[0] - v) <= tolerance:
                    bucket.append(v)
                    placed = True
                    break
            if not placed:
                buckets.append([v])
        repeated = sum(1 for b in buckets if len(b) >= 2)
        return repeated / max(1, len(buckets))

    return (repeat_ratio(xs) + repeat_ratio(ys)) / 2


def _classify_image(pil_image) -> dict:
    """Image-path classification: try a cheap table probe first (img2table),
    fall back to OpenCV line-density for CAD/drawing detection."""
    table_signal = _probe_table_image(pil_image)
    if table_signal["found"]:
        confidence = min(0.95, 0.5 + 0.1 * table_signal["table_count"])
        return {"type": "table", "confidence": round(confidence, 2), "signals": table_signal}

    line_signal = _line_density_image(pil_image)
    if line_signal["line_density"] > line_signal["threshold"]:
        confidence = min(0.95, 0.4 + line_signal["line_density"] * 50)
        return {"type": "cad_drawing", "confidence": round(confidence, 2), "signals": line_signal}

    return {"type": "unclassified", "confidence": 0.0, "signals": {**table_signal, **line_signal}}


def _probe_table_image(pil_image) -> dict:
    try:
        from img2table.document import Image as I2TImage
    except ImportError as e:
        raise RouterUnavailable(f"img2table not installed: {e}") from e

    import io
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)

    doc = I2TImage(buf.getvalue())
    tables = doc.extract_tables(implicit_rows=False, borderless_tables=False)
    table_count = len(tables)
    cell_counts = [len(t.content) for t in tables] if tables else []
    return {"found": table_count > 0, "table_count": table_count, "row_counts": cell_counts}


def _line_density_image(pil_image) -> dict:
    import cv2
    import numpy as np

    arr = np.array(pil_image.convert("L"))
    edges = cv2.Canny(arr, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=40, maxLineGap=5)
    line_count = 0 if lines is None else len(lines)
    area = arr.shape[0] * arr.shape[1]
    density = line_count / area * 1_000_000  # lines per megapixel, keeps the number readable
    return {"line_count": line_count, "line_density": round(density, 3), "threshold": 8.0}


def _rasterize_pdf_first_page(pdf_path: str):
    import fitz
    from PIL import Image as PILImage

    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
    image = PILImage.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return image


_I2T_OCR = None       # img2table's EasyOCR wrapper, used by extract_table_json()
_EASYOCR_READER = None  # raw easyocr.Reader, used by extract_cad_json()


def _get_i2t_ocr():
    """Lazy singleton — EasyOCR's model load is expensive (loads torch
    detection + recognition weights), so this only happens once per
    process, not once per document."""
    global _I2T_OCR
    if _I2T_OCR is None:
        try:
            from img2table.ocr import EasyOCR as I2TEasyOCR
        except ImportError as e:
            raise RouterUnavailable(f"easyocr not installed: {e}") from e
        _I2T_OCR = I2TEasyOCR(lang=["en"])
    return _I2T_OCR


def _get_easyocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
        except ImportError as e:
            raise RouterUnavailable(f"easyocr not installed: {e}") from e
        _EASYOCR_READER = easyocr.Reader(["en"])
    return _EASYOCR_READER


# --------------------------------------------------------------- table branch

def extract_table_json(file_path: str) -> dict:
    """
    Extracts every table found in the document and returns each one as a
    list of JSON records, keyed by whatever header row the table actually
    has — never a fixed/hardcoded set of field names. A different table
    layout produces different JSON keys.
    """
    try:
        from img2table.document import Image as I2TImage, PDF as I2TPDF
    except ImportError as e:
        raise RouterUnavailable(f"img2table not installed: {e}") from e

    ext = Path(file_path).suffix.lower()
    doc = I2TPDF(file_path) if ext in PDF_EXT else I2TImage(file_path)

    ocr = _get_i2t_ocr()
    extracted = doc.extract_tables(ocr=ocr, implicit_rows=True, borderless_tables=True)

    # img2table returns {page_index: [ExtractedTable, ...]} for PDFs and
    # [ExtractedTable, ...] directly for images — normalize both.
    if isinstance(extracted, dict):
        tables_flat = [t for page_tables in extracted.values() for t in page_tables]
    else:
        tables_flat = extracted

    tables_out = []
    for t in tables_flat:
        df = t.df
        if df.empty:
            continue
        header_idx, columns = _find_header_row(df)

        preamble_rows: list[list[Any]] = []
        data_rows_source = df
        if header_idx is not None:
            preamble_rows = [
                [_coerce_value(v) for v in df.iloc[i].tolist()] for i in range(header_idx)
            ]
            data_rows_source = df.iloc[header_idx + 1:]
        else:
            # No confident header row found — fall back to the raw
            # (still dynamic, never hardcoded) positional column labels.
            columns = [str(c).strip() or f"column_{i+1}" for i, c in enumerate(df.columns)]

        records = []
        for _, row in data_rows_source.iterrows():
            record = {}
            for col, val in zip(columns, row.tolist()):
                record[col] = _coerce_value(val)
            records.append(record)

        tables_out.append({
            "bbox": {"x1": t.bbox.x1, "y1": t.bbox.y1, "x2": t.bbox.x2, "y2": t.bbox.y2} if getattr(t, "bbox", None) else None,
            "preamble": preamble_rows,  # title-block / header text sitting above the real data grid, if any
            "columns": columns,
            "rowCount": len(records),
            "rows": records,
        })

    return {"tableCount": len(tables_out), "tables": tables_out}


def _find_header_row(df) -> tuple[Optional[int], Optional[list[str]]]:
    """
    Finds the most likely header row inside a table DataFrame, so a
    document like a title-blocked inspection report — where img2table
    correctly sees one continuous ruled grid spanning both the company
    letterhead AND the real data table — still produces clean per-column
    JSON instead of 9 generically-numbered columns.

    Heuristic (no document-specific assumptions):
      - A header row's cells are almost all distinct from each other.
        Preamble/letterhead rows are usually merged-cell repeats (the
        same company name spanning several columns), so their
        distinct-value ratio is low.
      - A header row is mostly non-numeric labels, unlike the data rows
        that follow it (quantities, weights, IDs).
      - We scan top-to-bottom and keep the last row that qualifies as
        "label-like" right before hitting the first clearly numeric
        (data) row — that's the header/data boundary.
    """
    header_idx = None
    for i in range(len(df)):
        vals = df.iloc[i].tolist()
        non_null = [v for v in vals if v is not None and str(v).strip().lower() != "nan"]
        if not non_null:
            continue
        uniqueness = len({str(v) for v in non_null}) / len(non_null)
        # "Contains a digit anywhere" rather than "is purely numeric" —
        # dimension codes, IDs, and dates ("5X1800X6300", "A259195",
        # "903257709 dtd 03.03.2023") all contain digits even though
        # they aren't clean numbers, and this stays reliable even when
        # OCR misses a couple of cells entirely (different OCR engines
        # fail on different cells) — a purely-numeric check would
        # wrongly disqualify a row just because its one clean integer
        # cell happened not to get read.
        has_digit_frac = sum(1 for v in non_null if re.search(r"\d", str(v))) / len(non_null)

        if uniqueness >= 0.6 and has_digit_frac < 0.3:
            header_idx = i
        elif header_idx is not None and has_digit_frac >= 0.3:
            break

    if header_idx is None:
        return None, None

    header_vals = df.iloc[header_idx].tolist()
    columns: list[str] = []
    seen: set[str] = set()
    for i, v in enumerate(header_vals):
        label = re.sub(r"\s+", " ", str(v)).strip() if v is not None and str(v).strip().lower() != "nan" else ""
        label = label or f"column_{i+1}"
        final = label
        n = 2
        while final in seen:
            final = f"{label}_{n}"
            n += 1
        seen.add(final)
        columns.append(final)
    return header_idx, columns


def _coerce_value(val: Any):
    """Turns whatever string img2table/OCR produced into the most specific
    JSON-native type it plausibly is, so the schema inference step can
    report real types (integer/number) instead of everything being a
    string. Falls back to string, never guesses a business meaning."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() in {"nan", "none"}:
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


# ---------------------------------------------------- table branch (OCR + LLM)

_PADDLE_OCR = None
OLLAMA_STRUCTURE_MODEL = os.environ.get("OLLAMA_STRUCTURE_MODEL", "qwen2.5:3b")


def _get_paddle_ocr():
    """Lazy singleton — PaddleOCR's model load is expensive. FLAGS_enable_pir_api
    must be set before the paddleocr import happens at all, not just before
    instantiation, so it's set here rather than at module load time."""
    global _PADDLE_OCR
    if _PADDLE_OCR is None:
        os.environ.setdefault("FLAGS_enable_pir_api", "0")
        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            raise RouterUnavailable(f"paddleocr not installed: {e}") from e
        _PADDLE_OCR = PaddleOCR(use_textline_orientation=True, lang="en", enable_mkldnn=False)
    return _PADDLE_OCR


def _paddle_ocr_tokens(file_path: str) -> list:
    """Runs PaddleOCR and returns raw [{"text": ..., "confidence": ...}, ...]
    tokens — no table-structure detection here, that's the LLM's job below.
    Uses PaddleOCR's own save_to_json/read-back round trip since that's the
    documented way to get plain-Python data out of its result object."""
    ocr = _get_paddle_ocr()
    result = ocr.predict(file_path)

    tokens = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_json_path = os.path.join(tmp_dir, "ocr_result.json")
        for res in result:
            if res is None:
                continue
            res.save_to_json(tmp_json_path)
            with open(tmp_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            texts = data.get("res", {}).get("rec_texts", data.get("rec_texts", []))
            scores = data.get("res", {}).get("rec_scores", data.get("rec_scores", []))
            for text, score in zip(texts, scores):
                tokens.append({"text": text, "confidence": round(float(score), 4)})
    return tokens


def _structure_tokens_with_llm(tokens: list) -> Optional[dict]:
    """
    Sends raw OCR tokens to a local Ollama model (qwen2.5:3b by default,
    override with OLLAMA_STRUCTURE_MODEL) and asks it to reconstruct them
    into a tabular JSON layout PLUS a short contextual summary.

    Deliberately gives the model NO example field names — earlier drafts
    of this prompt showed a worked example built around one specific
    document (an inspection report), and that biased the model toward
    reusing those exact field names on unrelated documents. The model is
    instead told to read the column headers out of the OCR tokens
    themselves and use those as JSON keys, so a different document
    produces different keys.

    Returns None (not an exception) on any failure — missing Ollama,
    unparseable JSON, timeout — so the caller can fall back to the
    geometric (img2table) extractor instead of failing the whole document.
    """
    try:
        import ollama
    except ImportError:
        return None

    prompt = f"""You are structuring raw OCR output from a scanned business/engineering document into JSON.

RAW OCR TOKENS (text + neural confidence per token, in reading order):
{json.dumps(tokens, indent=2)}

Do this:
1. Work out what kind of document this is and write a short "contextualSummary" (2-4 sentences): what the document is, who the parties/locations involved are, and any document-level identifiers (report numbers, dates, revisions) you can see.
2. If the tokens describe one or more tables, reconstruct each one as a list of row objects. The column names MUST come from whatever header row/labels actually appear in the OCR tokens — do not invent, translate, or standardize column names, and do not assume any particular document type's typical fields. A different document will have different columns; use exactly what's there.
3. For every extracted value, carry through the average confidence of the OCR token(s) it came from as "_confidence" (0-1 float) alongside the value in that row.

Return ONLY a single JSON object, no other text, in exactly this shape (the keys inside each row object are illustrative placeholders — replace them with the REAL column names you found):
{{
  "contextualSummary": "string",
  "tables": [
    {{
      "columns": ["<real column name 1>", "<real column name 2>", "..."],
      "rows": [
        {{"<real column name 1>": "value", "<real column name 2>": "value", "_confidence": 0.93}}
      ]
    }}
  ]
}}
If no tabular structure is present, return "tables": []."""

    # Scale the output budget with input size instead of a fixed guess —
    # a small nameplate and a 40-row BOM need very different headroom,
    # and a too-small budget silently truncates mid-JSON.
    approx_input_tokens = len(prompt) // 4
    predict_budget = max(2048, min(8192, approx_input_tokens * 2))

    try:
        response = ollama.chat(
            model=OLLAMA_STRUCTURE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.1, "num_ctx": 8192, "num_predict": predict_budget},
        )
        raw = response["message"]["content"]
        return json.loads(raw)
    except (json.JSONDecodeError, KeyError, Exception):
        return None


def extract_table_json_llm(file_path: str) -> dict:
    """
    Alternative to extract_table_json(): PaddleOCR pulls raw text +
    confidence tokens (no geometric table detection), then a local LLM
    reconstructs the tabular structure and writes a contextual summary.
    Falls back to extract_table_json() (img2table's grid-detection
    approach) if PaddleOCR or Ollama aren't available, or if the model's
    JSON output couldn't be parsed — so this never leaves a document
    with zero extraction just because the LLM had a bad run.
    """
    tokens = _paddle_ocr_tokens(file_path)
    if not tokens:
        return {"contextualSummary": None, "tableCount": 0, "tables": []}

    structured = _structure_tokens_with_llm(tokens)
    if structured is None or not isinstance(structured.get("tables"), list):
        fallback = extract_table_json(file_path)
        fallback["contextualSummary"] = None
        fallback["structuringMethod"] = "img2table_fallback"
        return fallback

    tables_out = []
    for t in structured.get("tables", []):
        columns = t.get("columns") or []
        rows_in = t.get("rows") or []
        rows_out = []
        for row in rows_in:
            record = {k: _coerce_value(v) for k, v in row.items() if k != "_confidence"}
            rows_out.append(record)
        tables_out.append({
            "columns": [str(c) for c in columns],
            "rowCount": len(rows_out),
            "rows": rows_out,
            # per-row OCR-derived confidence, kept separate from the data
            # itself so it doesn't pollute the dynamic schema of the row
            "rowConfidence": [row.get("_confidence") for row in rows_in],
        })

    return {
        "contextualSummary": structured.get("contextualSummary"),
        "structuringMethod": "llm",
        "tableCount": len(tables_out),
        "tables": tables_out,
    }


# ----------------------------------------------------------------- CAD branch

_KV_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9 ./_-]{1,40}?)\s*[:\-=]\s*(.+)$")


def extract_cad_json(file_path: str) -> dict:
    """
    OCRs a CAD/technical-drawing page and returns whatever it can read as
    JSON. Text that looks like "LABEL: VALUE" / "LABEL - VALUE" becomes a
    key/value pair (key = whatever label text was actually present, not a
    predefined one); everything else lands in a flat `annotations` list so
    nothing OCR found is thrown away, but nothing is force-mapped into a
    field that isn't really there.
    """
    try:
        reader = _get_easyocr_reader()
    except RouterUnavailable:
        raise

    ext = Path(file_path).suffix.lower()
    if ext in PDF_EXT:
        image = _rasterize_pdf_first_page(file_path)
    else:
        from PIL import Image as PILImage
        image = PILImage.open(file_path).convert("RGB")

    import numpy as np
    # paragraph=True merges nearby text into logical lines/blocks, which
    # is what the LABEL: VALUE line-matching below expects — the same
    # role pytesseract.image_to_string()'s newline-separated output played.
    lines = [ln.strip() for ln in reader.readtext(np.array(image), detail=0, paragraph=True) if ln.strip()]

    fields: dict[str, Any] = {}
    annotations: list[str] = []
    seen_keys: set[str] = set()

    for line in lines:
        m = _KV_PATTERN.match(line)
        if m:
            key_raw, value_raw = m.group(1).strip(), m.group(2).strip()
            key = re.sub(r"\W+", "_", key_raw.lower()).strip("_") or "field"
            # Duplicate labels (common on drawings, e.g. repeated "REV")
            # get a numeric suffix instead of overwriting each other.
            final_key = key
            n = 2
            while final_key in seen_keys:
                final_key = f"{key}_{n}"
                n += 1
            seen_keys.add(final_key)
            fields[final_key] = _coerce_value(value_raw)
        else:
            annotations.append(line)

    return {"fields": fields, "annotations": annotations}


# ------------------------------------------------------------- schema builder

def infer_json_schema(data: Any, title: str = "ExtractedDocument") -> dict:
    """
    Builds a JSON Schema (draft-07) purely by introspecting `data` — no
    field name or type is ever assumed ahead of time. Works on the output
    of extract_table_json(), extract_cad_json(), or any other JSON-shaped
    Python value.
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": title,
        **_infer_node(data),
    }


def _infer_node(value: Any) -> dict:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {}}
        # Merge the schemas of every item so a mixed-type or
        # occasionally-sparse array still produces one honest schema
        # instead of just inspecting item [0].
        item_schemas = [_infer_node(v) for v in value]
        merged = item_schemas[0]
        for s in item_schemas[1:]:
            merged = _merge_schemas(merged, s)
        return {"type": "array", "items": merged}
    if isinstance(value, dict):
        properties = {k: _infer_node(v) for k, v in value.items()}
        return {
            "type": "object",
            "properties": properties,
            "required": list(value.keys()),
        }
    return {"type": "string"}  # last-resort fallback, e.g. Decimal/date objects


def _merge_schemas(a: dict, b: dict) -> dict:
    if a == b:
        return a
    type_a = a.get("type")
    type_b = b.get("type")
    if type_a == "object" and type_b == "object":
        props = dict(a.get("properties", {}))
        for k, v in b.get("properties", {}).items():
            props[k] = _merge_schemas(props[k], v) if k in props else v
        required = sorted(set(a.get("required", [])) & set(b.get("required", [])))
        return {"type": "object", "properties": props, "required": required}
    # Types may already be a list from an earlier merge (e.g. a column
    # with both integer and string values across rows) — flatten before
    # deduping so this stays idempotent when merging 3+ schemas.
    types_a = type_a if isinstance(type_a, list) else [type_a]
    types_b = type_b if isinstance(type_b, list) else [type_b]
    types = sorted({t for t in (*types_a, *types_b) if t})
    return {"type": types if len(types) > 1 else types[0]}


# ---------------------------------------------------------------- entry point

def process_document(file_path: str) -> dict:
    """
    The single function callers need. Classifies the document, routes to
    the matching extractor, infers a schema from whatever came out, and
    returns one JSON-serializable result:

        {
          "documentType": "table" | "cad_drawing" | "unclassified",
          "classification": {...},   # confidence + signals, for debugging
          "schema": {...},           # JSON Schema, generated from `data`
          "data": {...}              # the actual extracted content
        }
    """
    classification = classify_layout(file_path)
    doc_type = classification["type"]

    if doc_type == "table":
        try:
            data = extract_table_json_llm(file_path)
        except RouterUnavailable:
            # PaddleOCR itself isn't installed -- geometric path still
            # needs its own OCR engine, so surface this rather than
            # silently trying a second extractor that will also fail.
            raise
        except Exception:
            # PaddleOCR ran but something else broke (Ollama down mid-run,
            # etc.) -- extract_table_json_llm already falls back internally
            # for a bad/missing LLM response; this catches anything else.
            data = extract_table_json(file_path)
    elif doc_type == "cad_drawing":
        data = extract_cad_json(file_path)
    else:
        data = {"reason": "Could not confidently classify this document as a table or a CAD drawing.", "signals": classification["signals"]}

    return {
        "documentType": doc_type,
        "classification": classification,
        "schema": infer_json_schema(data),
        "data": data,
    }
