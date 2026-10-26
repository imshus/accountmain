"""A copy of every uploaded document in Supabase Storage (optional).

When SUPABASE_URL and a secret key are set, each file a person uploads is also stored, byte for byte, in a
private Supabase Storage bucket. The copy is made in the background after the upload is saved, so it never slows
an upload down or makes it fail. Until Supabase confirms it, the file waits in a local outbox
(DATA_DIR/cloud_outbox), so a lost connection or a restart cannot lose the copy: passing failures are retried
(and again every 15 minutes while they last), copies left waiting are resumed when the backend starts, and only
problems that retrying cannot fix (wrong key, refused file, public bucket) are marked failed.
Copies are filed by register (uploads/sales/..., uploads/purchases/..., uploads/unsorted/...): at upload when the file
is clearly one register, else unsorted; when a sheet of it is added to the books, the copy goes to that register's
folder (moved within Supabase, never deleted and sent again; a failed move is retried like a copy).
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

from sqlalchemy import Column, DateTime, Integer, String, Table, Text, case, func, insert, select, update
from sqlalchemy.exc import OperationalError

from . import config, database

# One row per upload; kept when the upload is deleted here, because the copy in Supabase stays.
cloud_files = Table(
    "cloud_files",
    database.metadata,
    Column("dataset_id", Integer, primary_key=True),
    Column("filename", String(255), nullable=False),
    Column("bucket", String(100), nullable=False),
    Column("path", String(1024), nullable=False),  # where the copy is (done, or moving) or goes (waiting to be sent)
    Column("size_bytes", Integer, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("status", String(20), nullable=False),  # pending | done | failed
    Column("attempts", Integer, nullable=False),
    Column("error", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # Set while a copy in Supabase (at path) is to be moved to its register's folder: the status is then the move's
    # (pending, or failed). While the outbox still holds the file, the copy may be there or not (a send whose answer
    # was lost): it is moved if it is, else the file is sent to the new place.
    Column("move_to", String(1024)),
)

REGISTER_FOLDERS = ("sales", "purchases", "unsorted")

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
_again: set[int] = set()  # filed under a register while being sent: run once more when that send ends
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


def object_path(dataset_id: int, filename: str, when: datetime, sha256: str, register: str = "unsorted") -> str:
    """uploads/sales/2026-10/42-3f9a1c2b7d10-sales_register.xlsx

    The folder under uploads is the register the upload is filed under (sales, purchases or unsorted). The content
    fingerprint makes the name unique even when two servers (or a reset database) share a bucket and reuse upload ids,
    so a retry may overwrite only an identical file.
    """
    register = register if register in REGISTER_FOLDERS else "unsorted"
    name = f"{register}/{when:%Y-%m}/{dataset_id}-{sha256[:12]}-{_safe_name(filename)}"
    return f"{config.SUPABASE_FOLDER}/{name}" if config.SUPABASE_FOLDER else name


def _month(path: str) -> datetime:
    """The month a copy's path was made in (kept when it moves to another folder)."""
    found = re.search(r"(?:^|/)(\d{4})-(\d\d)/[^/]+$", path)
    return datetime(int(found.group(1)), int(found.group(2)), 1) if found and 1 <= int(found.group(2)) <= 12 else _now()


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


def _stored(bucket: str, path: str) -> bool:
    """Whether the bucket holds an object at ``path`` (from a listing of its folder)."""
    folder, _, name = path.rpartition("/")
    listed = _request("POST", f"{config.SUPABASE_URL}/storage/v1/object/list/{urllib.parse.quote(bucket, safe='')}",
                      json.dumps({"prefix": folder, "search": name, "limit": 100, "offset": 0}).encode(), "application/json")
    return isinstance(listed, list) and any(isinstance(item, dict) and item.get("name") == name for item in listed)


def _move_object(bucket: str, source: str, target: str) -> None:
    """Move an object to another name in the bucket: Supabase renames it, so it is never missing in between."""
    body = json.dumps({"bucketId": bucket, "sourceKey": source, "destinationKey": target}).encode()
    try:
        _request("POST", f"{config.SUPABASE_URL}/storage/v1/object/move", body, "application/json")
    except CloudError as exc:
        text = str(exc).lower()
        if "already exists" not in text and ("not found" not in text or "bucket" in text):
            raise
        # The answer to an earlier move was lost after it went through, or the same file (its name holds the content's
        # fingerprint) is already there: the copy is at the target. Nothing is ever deleted to make room.
        if _stored(bucket, target):
            return
        if "not found" in text:
            raise _Missing(f"the copy is no longer in Supabase at {source} or {target} (deleted there?); upload the "
                           "file again.", retry=False) from None
        raise


class _Missing(CloudError):
    """A move found the object at neither place."""


def _transaction(work):
    """``work(conn)`` in one transaction that waits out another writer (an upload storing a big sheet) instead of failing
    on 'database is locked'. Returns what it returns."""
    for pause in (0.5, 1, 2, 4, 8):
        try:
            with database.engine.begin() as conn:
                return work(conn)
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            time.sleep(pause)
    with database.engine.begin() as conn:
        return work(conn)


def _write(statement) -> int:
    """One write, as _transaction; returns the number of rows it changed."""
    return _transaction(lambda conn: conn.execute(statement).rowcount)


def _set(dataset_id: int, **values) -> None:
    _write(update(cloud_files).where(cloud_files.c.dataset_id == dataset_id).values(updated_at=_now(), **values))
    from .mongo_sync import touch  # mongo_sync imports this module

    touch("upload", dataset_id)  # MongoDB's copy of the upload shows the copy's new state (never raises)


def _row(dataset_id: int):
    with database.engine.connect() as conn:
        return conn.execute(select(*database.columns_of(cloud_files).values())
                            .where(cloud_files.c.dataset_id == dataset_id)).mappings().first()


def _wait(tried: int) -> None:
    if tried < ATTEMPTS_PER_RUN:
        time.sleep(_RETRY_DELAYS[min(tried - 1, len(_RETRY_DELAYS) - 1)])


def _send(dataset_id: int, row) -> bool:
    """Copy one outbox file to Supabase, retrying passing failures, and record the outcome; True once it is stored."""
    local = _outbox() / f"{dataset_id}"
    if not local.exists():
        _set(dataset_id, status="failed", error="The local copy waiting to be sent is missing; upload the file again.")
        return False
    content = local.read_bytes()
    if hashlib.sha256(content).hexdigest() != row["sha256"]:
        _set(dataset_id, status="failed", error="The local copy waiting to be sent is damaged; upload the file again.")
        return False
    attempts = row["attempts"]
    sent, c = row["path"], cloud_files.c
    # Filed under a register while this was sent (the row points elsewhere now): the copy is, or may be (an answer lost
    # after it arrived), where it was sent, and moves to the new place next.
    where = {"path": sent, "move_to": case((c.path == sent, c.move_to), else_=c.path)}
    for tried in range(1, ATTEMPTS_PER_RUN + 1):
        attempts += 1
        try:
            _put(row["bucket"], sent, content, row["filename"])
        except CloudError as exc:
            if not exc.retry:
                _set(dataset_id, status="failed", attempts=attempts, error=str(exc), **where)
                return False
            # A passing problem stays "pending": the sweeper tries again later, however long the outage lasts.
            _set(dataset_id, status="pending", attempts=attempts, error=str(exc), **where)
            _wait(tried)
            continue
        # Stored where it was sent: done, unless it is to move to its register's folder next.
        _set(dataset_id, attempts=attempts, error=None, status=case(((c.path == sent) & c.move_to.is_(None), "done"),
                                                                   else_="pending"), **where)
        local.unlink(missing_ok=True)
        return True
    return False


def _move(dataset_id: int, row) -> bool:
    """Move a copy already in Supabase to its register's folder, retrying passing failures like a copy. Until it has
    moved, the row keeps the place the copy really is. While the outbox still holds the file, a send to the old place may
    have arrived without an answer: a copy there is moved, and when there is none, True: the file is to be sent to the
    new place instead."""
    source, target, attempts = row["path"], row["move_to"], row["attempts"]
    local = _outbox() / f"{dataset_id}"
    for tried in range(1, ATTEMPTS_PER_RUN + 1):
        attempts += 1
        try:
            _move_object(row["bucket"], source, target)
        except CloudError as exc:
            if isinstance(exc, _Missing) and local.exists():
                _set(dataset_id, status="pending", attempts=attempts, error=None, path=target, move_to=None)
                return True
            error = f"Not yet moved to {target}: {exc}"
            if not exc.retry:
                _set(dataset_id, status="failed", attempts=attempts, error=error)
                return False
            _set(dataset_id, status="pending", attempts=attempts, error=error)
            _wait(tried)
            continue
        _set(dataset_id, status="done", attempts=attempts, error=None, path=target, move_to=None)
        local.unlink(missing_ok=True)  # a send whose answer was lost did arrive
        return False
    return False


def _run(dataset_id: int) -> None:
    """Copy one outbox file to Supabase, or move a copy there to its register's folder, then record the outcome."""
    row = _row(dataset_id)
    if row is None or row["status"] == "done":
        return
    if not row["move_to"]:
        if not _send(dataset_id, row):
            return
        row = _row(dataset_id)
        if row is None or not row["move_to"]:
            return
    if _move(dataset_id, row):
        row = _row(dataset_id)
        if row is not None:
            _send(dataset_id, row)


def _submit(dataset_id: int, again: bool = False) -> bool:
    """Start sending one copy in the background; False if it is already being sent (with ``again``: it runs once
    more when that send ends, for a change it may have missed)."""
    with _lock:
        if dataset_id in _active:
            if again:
                _again.add(dataset_id)
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
                rerun = dataset_id in _again
                _again.discard(dataset_id)
            if rerun:
                _submit(dataset_id)

    threading.Thread(target=work, name=f"cloud-{dataset_id}", daemon=True).start()
    return True


def enqueue(dataset_id: int, filename: str, content: bytes, register: str = "unsorted") -> None:
    """Keep the uploaded file in the outbox and start copying it to Supabase, into the folder of the register the
    upload is filed under (no-op when not configured)."""
    if not configured():
        return
    when = _now()
    sha = hashlib.sha256(content).hexdigest()
    row = {"dataset_id": dataset_id, "filename": filename, "bucket": config.SUPABASE_BUCKET,
           "path": object_path(dataset_id, filename, when, sha, register), "size_bytes": len(content), "sha256": sha,
           "status": "pending", "attempts": 0, "error": None, "updated_at": when, "move_to": None}
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


def _refile(conn, dataset_id: int, register: str) -> bool | None:
    """File the upload under ``register`` and point its copy at that register's folder, in one transaction (``conn``'s):
    None when an earlier import already filed it, else True when a copy that is, or may be, in Supabase must be moved."""
    d, c = database.datasets.c, cloud_files.c
    if not conn.execute(update(database.datasets).where((d.id == dataset_id) & d.register_added.is_not(True))
                        .values(register=register, register_added=True)).rowcount:
        return None
    try:
        row = conn.execute(select(c.filename, c.path, c.sha256).where(c.dataset_id == dataset_id)).first()
    except OperationalError as exc:
        if _table_missing(exc):
            return False
        raise
    if row is None:
        return False
    target = object_path(dataset_id, row.filename, _month(row.path), row.sha256, register)
    # Not in Supabase yet and never sent (waiting, or failed before any attempt): the outbox file simply goes to the new
    # place. A send already tried may have arrived without an answer, so that copy is moved like one in Supabase.
    if conn.execute(update(cloud_files).where((c.dataset_id == dataset_id) & (c.status != "done") & c.move_to.is_(None)
                                              & (c.attempts == 0)).values(path=target, updated_at=_now())).rowcount:
        return False
    # In Supabase (a copy that just arrived included), or perhaps: it moves, and the row says so until it has.
    return bool(conn.execute(update(cloud_files).where((c.dataset_id == dataset_id) & (c.path != target)).values(
        move_to=target, status="pending", attempts=0, error=None, updated_at=_now())).rowcount)


def set_register(dataset_id: int, register: str) -> None:
    """A sheet of this upload was added to the books as ``register`` (sales or purchases): file the upload under it,
    unless an earlier import already did (an upload with both registers stays under the first one added), and send its
    copy to that register's folder: one still waiting simply goes there, one already in Supabase is moved, in the
    background. Never raises: the import has succeeded either way."""
    try:
        move = _transaction(lambda conn: _refile(conn, dataset_id, register))
        if move is None:
            return
        from .mongo_sync import touch  # mongo_sync imports this module

        touch("upload", dataset_id)  # MongoDB's copy of the upload shows the register (never raises)
        if move and configured():
            _submit(dataset_id, again=True)
    except Exception as exc:  # noqa: BLE001 - the copy's folder must never turn a successful import into an error
        print(f"Upload {dataset_id} not filed under {register} ({type(exc).__name__}).")


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
        row = _row(dataset_id)
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
