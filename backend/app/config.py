"""Settings read from environment variables (and backend/.env if present)."""

from __future__ import annotations

import os
import re
import urllib.parse
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

# Optional: also keep every uploaded document in a private Supabase Storage bucket (app/cloud.py).
# Key: Supabase > Project Settings > API Keys > Secret keys (sb_secret_...); a legacy service_role key (eyJ...) also
# works until Supabase retires legacy keys. It stays on this server.
def _supabase_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    if url and "://" not in url:
        url = "https://" + url
    url = re.sub(r"/(rest|storage|auth)/v1(/.*)?$", "", url)  # the API URL pasted instead of the Project URL
    parts = urllib.parse.urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")  # the Supabase CLI runs on http://127.0.0.1:54321
    if url and parts.scheme != "https" and not local:
        print("SUPABASE_URL must start with https:// (the key must not travel unencrypted); Supabase copies are off.")
        return ""
    return url


def _supabase_key() -> str:
    key = (os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if any(c.isspace() or ord(c) < 32 for c in key):
        print("The Supabase key contains spaces or line breaks (copy it again in one line); Supabase copies are off.")
        return ""
    if key.startswith("sb_publishable_"):
        print("The Supabase key is a publishable key, which cannot write files; use a secret key. Supabase copies are off.")
        return ""
    return key


SUPABASE_URL = _supabase_url(os.getenv("SUPABASE_URL", ""))
SUPABASE_SERVICE_KEY = _supabase_key()
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "").strip() or "documents"
SUPABASE_FOLDER = re.sub(r"/+", "/", re.sub(r"[^A-Za-z0-9_/.-]+", "_", os.getenv("SUPABASE_FOLDER", "uploads"))).strip("/")

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
