"""Settings read from environment variables (and backend/.env if present)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "accounts.db"

# Which chat model the app uses when more than one is configured: "openai" or "anthropic".
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# Speed with accuracy: answers start at low effort (about twice as fast as high on this app's questions),
# because the numbers come from the tools and every figure is checked. If a figure fails the check, the
# correction round runs at medium effort.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "low")
OPENAI_REPAIR_EFFORT = os.getenv("OPENAI_REPAIR_EFFORT", "medium")
# Short answers are written (and arrive) sooner: low | medium | high.
OPENAI_VERBOSITY = os.getenv("OPENAI_VERBOSITY", "low").strip() or None
# Optional: "priority" asks OpenAI for faster processing at a higher price per token.
OPENAI_SERVICE_TIER = os.getenv("OPENAI_SERVICE_TIER", "").strip() or None

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
ANTHROPIC_EFFORT = os.getenv("ANTHROPIC_EFFORT", "low")
ANTHROPIC_REPAIR_EFFORT = os.getenv("ANTHROPIC_REPAIR_EFFORT", "medium")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".csv"}

# Rows returned to the browser for previews and SQL results.
PREVIEW_ROWS = 50
SQL_RESULT_LIMIT = 500
SQL_TIMEOUT_SECONDS = 10

# Pages allowed to call the API: the development frontend, and the Android app (its pages are served
# from http://localhost inside the app). Add the address of a hosted frontend here if you deploy one.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost,https://localhost,capacitor://localhost"
    ).split(",")
    if origin.strip()
]


def openai_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def anthropic_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
