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
# The suggested next questions under an answer: a short call without tools, so little reasoning is needed.
OPENAI_FOLLOWUP_EFFORT = os.getenv("OPENAI_FOLLOWUP_EFFORT", "low")
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

# Optional: a live copy of the app's records (uploads with their sheets' statistics, notes and setup; chat
# conversations) in MongoDB (app/mongo_sync.py); SQLite stays the main copy.
# MONGODB_URI: MongoDB Atlas > Connect > Drivers, the mongodb+srv://user:password@... string. It holds a password, so it
# stays on this server and is never printed: messages name only the host.
def _mongodb_parts(uri: str) -> tuple[list[str], dict[str, str]] | None:
    """Host names and options (lower case) of a connection string, split the way the driver splits it; None when a
    host is not a plain name (often a '/', '@' or ':' in the password that is not percent-encoded)."""
    authority, _, tail = uri.partition("://")[2].partition("/")
    path, _, query = tail.partition("?")
    names = []
    for host in authority.rpartition("@")[2].split(","):
        match = re.fullmatch(r"\[([0-9A-Fa-f:.]+)\](?::\d+)?|([A-Za-z0-9._-]+)(?::\d+)?", host)
        if not match:
            return None
        names.append(match.group(1) or match.group(2))
    if "@" in path:  # part of a password with an unescaped '/'
        return None
    return names, {k.lower(): v.lower() for k, v in urllib.parse.parse_qsl(query.replace(";", "&"))}


def mongodb_hosts(uri: str) -> str:
    """The host names in a connection string, for messages (never the user name or password)."""
    parts = _mongodb_parts(uri) if uri else None
    return ", ".join(parts[0]) if parts else ""


def _mongodb_uri(raw: str) -> str:
    uri = raw.strip()
    if not uri:
        return ""
    if any(c.isspace() or ord(c) < 32 for c in uri):
        print("MONGODB_URI contains spaces or line breaks (copy it again in one line); MongoDB sync is off.")
        return ""
    scheme = uri.partition("://")[0] if "://" in uri else ""
    if scheme not in ("mongodb", "mongodb+srv"):
        print("MONGODB_URI must start with mongodb+srv:// (MongoDB Atlas) or mongodb://; MongoDB sync is off.")
        return ""
    parts = _mongodb_parts(uri)
    if parts is None:
        print("MONGODB_URI has no valid host name (percent-encode the password, e.g. with Python's "
              "urllib.parse.quote_plus: @ as %40, : as %3A, / as %2F, ? as %3F, + as %2B, % as %25); MongoDB sync is off.")
        return ""
    names, options = parts
    tls = {options[k] for k in ("tls", "ssl") if k in options}
    encrypted = tls == {"true"} if tls else scheme == "mongodb+srv"  # mongodb+srv:// turns TLS on unless told not to
    unchecked = any(options.get(k) == "true" for k in ("tlsinsecure", "tlsallowinvalidcertificates", "tlsallowinvalidhostnames"))
    if not all(name in ("localhost", "127.0.0.1", "::1") for name in names) and (not encrypted or unchecked):
        print(f"MONGODB_URI for {', '.join(names)} must use TLS with certificate checks (the mongodb+srv:// string from "
              "Atlas, or tls=true): the password must not travel unencrypted; MongoDB sync is off.")
        return ""
    return uri


MONGODB_URI = _mongodb_uri(os.getenv("MONGODB_URI", ""))
MONGODB_DB = os.getenv("MONGODB_DB", "").strip() or "accountsai"

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
