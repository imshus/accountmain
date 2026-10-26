"""A copy of every uploaded document in Supabase Storage (optional).

When SUPABASE_URL and a secret key are set, each file a person uploads is also stored, byte for byte, in a
private Supabase Storage bucket. The copy is made in the background after the upload is saved, so it never slows
an upload down or makes it fail. Until Supabase confirms it, the file waits in a local outbox
(DATA_DIR/cloud_outbox), so a lost connection or a restart cannot lose the copy: passing failures are retried
(and again every 15 minutes while they last), copies left waiting are resumed when the backend starts, and only
problems that retrying cannot fix (wrong key, refused file, public bucket) are marked failed.
Standard library only, so it runs on every supported Python.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import mimetypes
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, String, Table, Text, func, insert, select, update
from sqlalchemy.exc import OperationalError

from . import config, database

# One row per upload; kept when the upload is deleted here, because the copy in Supabase stays.
cloud_files = Table(
    "cloud_files",
    database.metadata,
    Column("dataset_id", Integer, primary_key=True),
    Column("filename", String(255), nullable=False),
    Column("bucket", String(100), nullable=False),
    Column("path", String(1024), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("status", String(20), nullable=False),  # pending | done | failed
    Column("attempts", Integer, nullable=False),
    Column("error", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

ATTEMPTS_PER_RUN = 5
_RETRY_DELAYS = (2, 10, 30, 120)  # seconds between attempts within one run
_SWEEP_SECONDS = 15 * 60  # copies still waiting after a run are tried again this often
_TIMEOUT = 60
# Answers that trying again cannot fix: bad request or name, wrong key, no permission, file refused, and
# redirects (the key must never follow one, see _NoRedirect).
_FINAL = {301, 302, 303, 307, 308, 400, 401, 403, 413, 415, 422}
_MIME = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
}

# Two copies at a time, on daemon threads: a copy waiting to retry must never hold up a restart (pm2, --reload);
# the outbox keeps the file, so an interrupted copy is simply sent again on the next start.
_slots = threading.BoundedSemaphore(2)
_lock = threading.Lock()
_active: set[int] = set()  # copies being sent now (never start a second send of the same file)
_checked_buckets: set[str] = set()  # buckets known to exist and be private
_sweeper_started = False


class CloudError(Exception):
    """A copy failed; ``retry`` is False when trying again cannot help (wrong key, refused file)."""

    def __init__(self, message: str, retry: bool = True):
        super().__init__(message)
        self.retry = retry


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: urllib would resend the key to wherever it points, and turn the upload into a GET."""

    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _outbox() -> Path:
    return config.DATA_DIR / "cloud_outbox"


def _safe_name(filename: str) -> str:
    """Storage object names: letters, digits, dot, dash and underscore, keeping the extension."""
    stem, suffix = os.path.splitext(Path(unicodedata.normalize("NFKC", filename)).name)
    suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix).lower()[:10]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")[:120] or "upload"
    return stem + suffix


def object_path(dataset_id: int, filename: str, when: datetime, sha256: str) -> str:
    """uploads/2026-10/42-3f9a1c2b7d10-sales_register.xlsx

    The content fingerprint makes the name unique even when two servers (or a reset database) share a bucket and
    reuse upload ids, so a retry may overwrite only an identical file.
    """
    name = f"{when:%Y-%m}/{dataset_id}-{sha256[:12]}-{_safe_name(filename)}"
    return f"{config.SUPABASE_FOLDER}/{name}" if config.SUPABASE_FOLDER else name


def _request(method: str, url: str, body: bytes | None, content_type: str | None = None, extra: dict | None = None) -> dict:
    key = config.SUPABASE_SERVICE_KEY
    # apikey for Supabase's gateway; the same value as Bearer, as supabase-js sends (works for legacy service_role
    # JWTs and for the newer sb_secret_ keys).
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if content_type:
        headers["Content-Type"] = content_type
    headers.update(extra or {})
    try:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        with _opener.open(req, timeout=_TIMEOUT) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read() or b""
        try:
            detail = json.loads(raw or b"{}")
        except ValueError:
            detail = {}
        if not isinstance(detail, dict):
            detail = {}
        if 300 <= exc.code < 400:
            raise CloudError(f"SUPABASE_URL redirects ({exc.code}); set it to the https:// Project URL.", retry=False) from None
        message = str(detail.get("message") or detail.get("error") or raw[:200].decode("utf-8", "replace") or exc.reason)
        # Supabase Storage puts its own status in the body (e.g. "404" for a missing bucket inside an HTTP 400).
        code = str(detail.get("statusCode") or exc.code)
        status = int(code) if code.isdigit() else exc.code
        raise CloudError(f"Supabase answered {status}: {message}", retry=status not in _FINAL) from None
    except (ValueError, http.client.HTTPException) as exc:
        # Never str(exc) here: a malformed header error would contain the key.
        raise CloudError(f"Bad request to Supabase ({type(exc).__name__}): check SUPABASE_URL and the key in backend/.env.",
                         retry=isinstance(exc, http.client.HTTPException)) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CloudError(f"Could not reach Supabase: {getattr(exc, 'reason', type(exc).__name__)}") from None
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        return {}


def _ensure_bucket(bucket: str) -> None:
    """Create the bucket (private) the first time; refuse to store documents in a public one."""
    with _lock:
        if bucket in _checked_buckets:
            return
    base = config.SUPABASE_URL
    try:
        info = _request("GET", f"{base}/storage/v1/bucket/{urllib.parse.quote(bucket, safe='')}", None)
    except CloudError as exc:
        if "not found" not in str(exc).lower():
            raise
        try:
            _request("POST", f"{base}/storage/v1/bucket", json.dumps({"id": bucket, "name": bucket, "public": False}).encode(),
                     "application/json")
        except CloudError as created:
            if "already exists" not in str(created).lower():
                raise
        info = {"public": False}
    if info.get("public"):
        raise CloudError(f"Supabase bucket '{bucket}' is public, so anyone could download these documents. Make it private "
                         "(Supabase > Storage > bucket > Edit) or set SUPABASE_BUCKET to a private bucket.", retry=False)
    with _lock:
        _checked_buckets.add(bucket)


def _put(bucket: str, path: str, content: bytes, filename: str) -> None:
    _ensure_bucket(bucket)
    url = f"{config.SUPABASE_URL}/storage/v1/object/{urllib.parse.quote(bucket, safe='')}/{urllib.parse.quote(path, safe='/')}"
    content_type = _MIME.get(Path(filename).suffix.lower()) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        # x-upsert: a retry after a lost reply overwrites the same (identical) object instead of failing as a duplicate.
        _request("POST", url, content, content_type, {"x-upsert": "true", "cache-control": "private, max-age=3600"})
    except CloudError as exc:
        if "bucket not found" in str(exc).lower():
            with _lock:
                _checked_buckets.discard(bucket)  # deleted since it was checked: create it again on the next attempt
            raise CloudError(str(exc), retry=True) from None
        raise


def _write(statement) -> None:
    """A write that waits out another writer (an upload storing a big sheet) instead of failing on 'database is locked'."""
    for pause in (0.5, 1, 2, 4, 8):
        try:
            with database.engine.begin() as conn:
                conn.execute(statement)
            return
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            time.sleep(pause)
    with database.engine.begin() as conn:
        conn.execute(statement)


def _set(dataset_id: int, **values) -> None:
    _write(update(cloud_files).where(cloud_files.c.dataset_id == dataset_id).values(updated_at=_now(), **values))
    from .mongo_sync import touch  # mongo_sync imports this module

    touch("upload", dataset_id)  # MongoDB's copy of the upload shows the copy's new state (never raises)


def _run(dataset_id: int) -> None:
    """Copy one outbox file to Supabase, retrying passing failures, then record the outcome."""
    with database.engine.connect() as conn:
        row = conn.execute(select(cloud_files).where(cloud_files.c.dataset_id == dataset_id)).mappings().first()
    if row is None or row["status"] == "done":
        return
    local = _outbox() / f"{dataset_id}"
    if not local.exists():
        _set(dataset_id, status="failed", error="The local copy waiting to be sent is missing; upload the file again.")
        return
    content = local.read_bytes()
    if hashlib.sha256(content).hexdigest() != row["sha256"]:
        _set(dataset_id, status="failed", error="The local copy waiting to be sent is damaged; upload the file again.")
        return
    attempts = row["attempts"]
    for tried in range(1, ATTEMPTS_PER_RUN + 1):
        attempts += 1
        try:
            _put(row["bucket"], row["path"], content, row["filename"])
        except CloudError as exc:
            if not exc.retry:
                _set(dataset_id, status="failed", attempts=attempts, error=str(exc))
                return
            # A passing problem stays "pending": the sweeper tries again later, however long the outage lasts.
            _set(dataset_id, status="pending", attempts=attempts, error=str(exc))
            if tried < ATTEMPTS_PER_RUN:
                time.sleep(_RETRY_DELAYS[min(tried - 1, len(_RETRY_DELAYS) - 1)])
            continue
        _set(dataset_id, status="done", attempts=attempts, error=None)
        local.unlink(missing_ok=True)
        return


def _submit(dataset_id: int) -> bool:
    """Start sending one copy in the background; False if it is already being sent."""
    with _lock:
        if dataset_id in _active:
            return False
        _active.add(dataset_id)

    def work():
        try:
            with _slots:
                _run(dataset_id)
        except Exception as exc:  # noqa: BLE001 - a background copy must never take the server down
            try:
                # Left pending (not failed) so the next sweep tries again; no raw text, which could hold SQL or a key.
                _set(dataset_id, status="pending", error=f"Unexpected error ({type(exc).__name__}); will retry.")
            except Exception:  # noqa: BLE001
                pass
        finally:
            with _lock:
                _active.discard(dataset_id)

    threading.Thread(target=work, name=f"cloud-{dataset_id}", daemon=True).start()
    return True


def enqueue(dataset_id: int, filename: str, content: bytes) -> None:
    """Keep the uploaded file in the outbox and start copying it to Supabase (no-op when not configured)."""
    if not configured():
        return
    when = _now()
    sha = hashlib.sha256(content).hexdigest()
    row = {"dataset_id": dataset_id, "filename": filename, "bucket": config.SUPABASE_BUCKET,
           "path": object_path(dataset_id, filename, when, sha), "size_bytes": len(content), "sha256": sha,
           "status": "pending", "attempts": 0, "error": None, "updated_at": when}
    # The file reaches the disk in full before the row that points at it exists (a power cut cannot leave a
    # truncated file marked as waiting).
    _outbox().mkdir(parents=True, exist_ok=True)
    temp, final = _outbox() / f"{dataset_id}.part", _outbox() / f"{dataset_id}"
    with open(temp, "wb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temp, final)
    try:
        _write(insert(cloud_files).prefix_with("OR REPLACE").values(**row))
    except Exception:
        final.unlink(missing_ok=True)
        raise
    _submit(dataset_id)


def _sweep_forever() -> None:
    while True:
        time.sleep(_SWEEP_SECONDS)
        try:
            resume()
        except Exception:  # noqa: BLE001 - keep sweeping
            pass


def _table_missing(exc: OperationalError) -> bool:
    """The table could not be created at startup (a read-only data folder): there are no copies to report."""
    return "no such table" in str(exc)


def resume() -> int:
    """Send copies still waiting (at startup, and every 15 minutes while any wait); returns how many started."""
    global _sweeper_started
    if not configured():
        return 0
    with _lock:
        if not _sweeper_started:
            _sweeper_started = True
            threading.Thread(target=_sweep_forever, name="cloud-sweeper", daemon=True).start()
    try:
        with database.engine.connect() as conn:
            ids = conn.execute(select(cloud_files.c.dataset_id).where(cloud_files.c.status == "pending")).scalars().all()
    except OperationalError as exc:
        if _table_missing(exc):
            return 0
        raise
    return sum(_submit(dataset_id) for dataset_id in ids)


def retry_failed() -> int:
    """Send every failed copy again (e.g. after fixing the key or making the bucket private)."""
    if not configured():
        return 0
    with database.engine.connect() as conn:
        ids = conn.execute(select(cloud_files.c.dataset_id).where(cloud_files.c.status == "failed")).scalars().all()
    if ids:
        _write(update(cloud_files).where(cloud_files.c.dataset_id.in_(ids)).values(status="pending", attempts=0, updated_at=_now()))
    with _lock:
        _checked_buckets.clear()
    return sum(_submit(dataset_id) for dataset_id in ids)


def _utc(when: datetime | None) -> datetime | None:
    """SQLite drops the time zone; the values were written in UTC."""
    return when.replace(tzinfo=timezone.utc) if when is not None and when.tzinfo is None else when


def status_of(dataset_id: int) -> dict | None:
    try:
        with database.engine.connect() as conn:
            row = conn.execute(select(cloud_files).where(cloud_files.c.dataset_id == dataset_id)).mappings().first()
    except OperationalError as exc:
        if _table_missing(exc):
            return None
        raise
    if row is None:
        return None
    return {"status": row["status"], "bucket": row["bucket"], "path": row["path"], "error": row["error"],
            "updated_at": _utc(row["updated_at"])}


def summary() -> dict:
    counts = {"pending": 0, "done": 0, "failed": 0}
    try:
        with database.engine.connect() as conn:
            for status, count in conn.execute(select(cloud_files.c.status, func.count()).group_by(cloud_files.c.status)):
                counts[status] = count
    except OperationalError as exc:
        if not _table_missing(exc):
            raise
    return {"configured": configured(), "provider": "supabase" if configured() else None,
            "bucket": config.SUPABASE_BUCKET if configured() else None, **counts}
