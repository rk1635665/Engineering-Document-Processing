# EDPS Backend (FastAPI)

Backend for the Engineering Document Processing System frontend. No auth,
single SQLite file, built specifically so your separate extraction
pipeline (nameplate OCR / P&ID tag detection) has two clear places to
push results into.

## Setup

```bash
cd edcs-backend
python3 -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt

python -m app.seed               # loads demo data matching the old mock JSON
uvicorn app.main:app --reload --port 8000
```

API docs (interactive, auto-generated): http://localhost:8000/docs

## Wiring up the frontend

The frontend now calls this API directly on every page (Dashboard,
Documents, Upload, Document Viewer, Extracted Data, Review &
Validation, Compare Revisions) — no more `mockY` imports in the data
path. `VITE_API_BASE_URL` (see `.env`) points it at this server.

Nothing else about the frontend changed — Table, Card, StatusBadge,
ConfidenceBadge, Sidebar, Navbar all work exactly as before, since the
API returns the same field names the mock JSON used (camelCase
throughout, via `CamelModel`'s alias generator).

## The extraction pipeline is live

`app/extraction_pipeline.py` runs automatically as a background task
right after `POST /api/documents/upload` — no separate polling process
needed. It moves a document through `queued -> processing ->
review|completed` (or `failed`, with the reason in `reviewerComment`)
by itself:

1. **OCR** — Florence-2 (`OCR_WITH_REGION`) over the uploaded image, or
   the rasterized first page for PDFs.
2. **Classification** — P&ID / Nameplate / General Arrangement, decided
   from how many instrument-tag-shaped tokens and nameplate keywords
   the OCR pass actually found (see `_classify`).
3. **Attribute extraction** — part numbers, material, dimensions, and
   tolerance are pulled out of the OCR text with pattern matching
   (`_extract_attributes`), not hardcoded per file.
4. **Confidence scoring** — a shape-based heuristic
   (`_heuristic_region_confidence`) drives every confidence value shown
   in the UI; nothing is a fixed number.

Results are written straight into `ExtractedPart` / `ReviewField` — the
same two tables the two integration endpoints below write to, so you
can still push results from an external process instead if you'd
rather run the pipeline elsewhere (e.g. on a machine with a GPU).

This needs the ML deps in `requirements-extraction.txt`
(torch/transformers/timm/einops/pymupdf) — see that file for the
install command. Without them, uploads land on `status="failed"` with
an honest "OCR dependencies not installed" message instead of
fabricating extraction results.

### Manual integration endpoints (still available)

If you'd rather run OCR as its own process (e.g. so it can use a GPU
box separate from the API server), these two endpoints are the same
integration surface as before:

**`POST /api/documents/{id}/parts`** — one or more detected parts/tags
for a document (a P&ID drawing can report several in one call):
```json
{
  "parts": [
    { "partNumber": "PIC-2210", "material": "SS316", "dimensions": "1/2 in NPT", "tolerance": "±0.05 mm", "confidence": 93 }
  ],
  "status": "review"
}
```

**`POST /api/documents/{id}/review-fields`** — flat field/value/confidence
breakdown for a document that needs human review (typically a
nameplate's individual fields):
```json
{
  "fields": [
    { "fieldKey": "part_number", "label": "Part Number", "value": "PSV-500A", "confidence": 97 }
  ],
  "status": "review"
}
```

Both accept an optional `status` to flip the document's StatusBadge in
the same call (`"processing"`, `"review"`, `"completed"`, `"failed"`).
If your pipeline runs as a separate process, poll
`GET /api/documents?status=queued` to find work, or watch the
`uploads/` folder directly — `file_path` on each Document record points
at the saved upload.

## Endpoint reference

| Method | Path | Used by |
|---|---|---|
| GET | `/api/dashboard/stats` | Dashboard stat cards |
| GET | `/api/documents` | Dashboard recent docs, Documents page (`?status=&type=&search=`) |
| GET | `/api/documents/{id}` | Document detail, incl. `extractedFields` + `fileUrl` |
| GET | `/api/documents/{id}/download` | Download buttons |
| POST | `/api/documents/upload` | Upload Documents page (multipart: `file`, `type`, `revision`) — schedules extraction automatically |
| PATCH | `/api/documents/{id}/status` | Manual status override |
| DELETE | `/api/documents/{id}` | Remove from queue |
| GET | `/api/parts` | Extracted Data page (`?search=&confidence=&revision=&documentType=`) |
| GET | `/api/parts/export` | "Export CSV" button — same filters as above |
| GET | `/api/documents/{id}/parts` | Parts for one document |
| POST | `/api/documents/{id}/parts` | **Manual pipeline: push detected parts** |
| GET | `/api/documents/{id}/review-fields` | Review & Validation page |
| POST | `/api/documents/{id}/review-fields` | **Manual pipeline: push field breakdown** |
| PUT | `/api/documents/{id}/review-fields/{fieldId}` | Human edits a value |
| POST | `/api/documents/{id}/review` | Approve/Reject buttons (`{"status": "approved"\|"rejected", "comment": "..."}`) |
| GET | `/api/revisions` | Compare Revisions dropdowns |
| GET | `/api/compare` | Compare Revisions diff (`?docA=&docB=`, document IDs) — real diff over each doc's parts/fields |
| POST | `/api/documents/{id}/chat` | AI Chat panel — grounded on that document's `extractedFields`/parts |
| GET | `/api/notifications` | Navbar bell dropdown |
| POST | `/api/notifications/read-all` | "Mark all read" |

## What's intentionally left as a placeholder

- **Dashboard trend values** (`"+8.2% vs last week"`) are placeholders.
  Computing a real trend needs a historical snapshot table, which isn't
  built yet — the current values (`total_documents`, `extraction_accuracy`,
  etc.) are all live, just not the deltas.
- **Notifications** are seeded once and don't get created automatically
  when documents change status. Add a call to create a `Notification`
  row wherever that matters to you (e.g. inside the `/parts` or
  `/review-fields` push endpoints).

## Notes

- CORS is open to `http://localhost:5173` by default (Vite's dev
  server). Set the `CORS_ORIGINS` env var (comma-separated) before
  deploying.
- SQLite file lives at `edcs.db` in this folder — delete it and re-run
  `python -m app.seed` to reset to demo data.
- Uploaded files are saved to `uploads/` and served back at
  `/files/<filename>`.
