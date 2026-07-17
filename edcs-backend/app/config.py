import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{BASE_DIR / 'edcs.db'}"

# The Vite dev server default + a couple of common alternates. Add your
# production frontend origin here (or set CORS_ORIGINS env var, comma
# separated) before deploying.
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", DEFAULT_ORIGINS).split(",")

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB, matches the Upload page's stated limit
ACCEPTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
