from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, UPLOAD_DIR
from .database import Base, engine
from .routers import documents, extraction, dashboard, compare, notifications, chat

# Creates tables on first run if they don't exist yet. Run `python -m
# app.seed` separately to load demo data matching the old mock JSON.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="EDPS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves uploaded files back for previews, e.g. /files/doc-1042.jpg
app.mount("/files", StaticFiles(directory=str(UPLOAD_DIR)), name="files")

app.include_router(documents.router)
app.include_router(extraction.router)
app.include_router(dashboard.router)
app.include_router(compare.router)
app.include_router(notifications.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
