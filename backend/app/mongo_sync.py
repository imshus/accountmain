"""A live copy of the app's records in MongoDB (optional).

When MONGODB_URI is set, every upload (file name, size, the register it is filed under, and each sheet's statistics,
notes and report setup, plus the state of its Supabase copy) and every chat conversation is also kept in MongoDB, in the collections "uploads" and
"chats" of MONGODB_DB (MongoDB Atlas or a server of your own). SQLite stays the main copy; the books, the vouchers and
the sheets' rows are not copied. A change only marks the record in memory, and one background thread writes the
record's state as it is then (or deletes it once it is gone), so MongoDB never slows a request down or makes it fail,
and sending a record twice is harmless. Records still to send wait in the mongo_sync table: passing failures (MongoDB
or the network down) keep them waiting and are retried after growing pauses, and a pass at startup and every 5 minutes
compares every record with what MongoDB last confirmed (for the hosts and database set now) and with the ids MongoDB
holds, so records made before MongoDB was set up, a change no hook reported, a new MONGODB_DB or cluster and a
collection emptied in Atlas still get every record. Only problems that retrying cannot fix (wrong password, no
permission, unusable address, a record MongoDB refuses) are marked failed; POST /api/mongo/retry, or a restart, tries
those again. The connection string holds a password, so no message, row or log line ever contains it: messages name
only the host.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.parse
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Table, Text, func, select, update
from sqlalchemy.dialects.sqlite import insert as upsert
from sqlalchemy.exc import OperationalError

from . import cloud, config, database, reports

# One row per record ever marked for MongoDB; synced_hash is the fingerprint of the state MongoDB last confirmed
# (with the hosts and database it went to).
mongo_sync = Table(
    "mongo_sync",
    database.metadata,
    Column("kind", String(10), primary_key=True),  # upload | chat
    Column("key", String(120), primary_key=True),  # the upload id, or "<scope>/<conversation id>"
    Column("status", String(20), nullable=False),  # pending | done | failed
    Column("attempts", Integer, nullable=False),
    Column("error", Text),
    Column("synced_hash", String(64)),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

GONE = "deleted"  # synced_hash of a record deleted from MongoDB
_SWEEP_SECONDS = 5 * 60  # every record is compared with MongoDB's copy, and waiting ones are tried again, this often
_BACKOFF = (5, 15, 60, 120, 300)  # seconds to wait after the 1st, 2nd... passing failure in a row
# One client for the whole process (it is thread-safe and keeps its own connections). connect=False: nothing is looked
# up (mongodb+srv:// addresses need DNS) or opened before the first write.
_CLIENT_OPTIONS = {"serverSelectionTimeoutMS": 5000, "connectTimeoutMS": 5000, "socketTimeoutMS": 30000,
                   "appname": "Accounts.ai", "retryWrites": True, "connect": False}
# Server answers that pass: a primary stepping down or shutting down, a host unreachable, an operation timed out.
_PASSING_CODES = {6, 7, 50, 89, 91, 189, 262, 9001, 10107, 11600, 11602, 13435, 13436}
_COLLECTIONS = {"upload": "uploads", "chat": "chats"}

_marks_lock = threading.Lock()  # held only for a set operation: a request never waits on MongoDB
_client_lock = threading.Lock()
_marked: set[tuple[str, str]] = set()  # changed records not yet written to mongo_sync
_wake = threading.Event()  # a record was marked
_hurry = threading.Event()  # failed records were queued again by hand: end a pause after a passing failure
_client = None  # the pymongo client, made by the first write
_worker: threading.Thread | None = None


class SyncError(Exception):
    """A write to MongoDB failed; ``retry`` is False when trying again cannot help (wrong password, refused record)."""

    def __init__(self, message: str, retry: bool = True):
        super().__init__(message)
        self.retry = retry


def configured() -> bool:
    return bool(config.MONGODB_URI)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hosts() -> str:
    return config.mongodb_hosts(config.MONGODB_URI) or "the MONGODB_URI host"


def _safe(text: str) -> str:
    """A driver or server message without the connection string, its password, or any scheme://user:password@."""
    uri = config.MONGODB_URI
    password = uri.partition("://")[2].partition("/")[0].rpartition("@")[0].partition(":")[2]
    secrets = {uri, password, urllib.parse.unquote(password), urllib.parse.unquote_plus(password)}
    for secret in sorted(secrets, key=len, reverse=True):
        if len(secret) >= 4:
            text = text.replace(secret, "***")
    return re.sub(r"([A-Za-z][A-Za-z0-9+.-]*://)[^\s/]*@", r"\1***@", text)[:300]


def _sync_error(exc: Exception) -> SyncError:
    """A driver error as a short message that is safe to store and show, and whether trying again can help."""
    from bson.errors import InvalidDocument  # DocumentTooLarge too
    from pymongo import errors

    kind = type(exc).__name__
    if isinstance(exc, errors.ConfigurationError) and type(exc.__cause__).__module__.split(".")[0] == "dns":
        # mongodb+srv:// addresses are looked up in DNS by the first write: no network, or no DNS answer yet.
        return SyncError(f"Could not look up {_hosts()} in DNS ({type(exc.__cause__).__name__}); will retry. If this "
                         "lasts, check the cluster address in MONGODB_URI.")
    if isinstance(exc, errors.ConnectionFailure):  # AutoReconnect, NetworkTimeout, ServerSelectionTimeoutError
        reason = _safe(str(exc)).split(", Timeout:")[0].split(" (configured timeouts")[0][:200]
        return SyncError(f"Could not reach MongoDB at {_hosts()} ({kind}: {reason}); will retry. If this lasts, check "
                         "that this server's IP address is on the Atlas Network Access list.")
    if isinstance(exc, errors.OperationFailure):
        message = _safe(str((exc.details or {}).get("errmsg") or str(exc).split(", full error")[0]))[:200]
        code = exc.code
        if (isinstance(exc, (errors.ExecutionTimeout, errors.WriteConcernError)) or code in _PASSING_CODES
                or exc.has_error_label("RetryableWriteError")):
            return SyncError(f"MongoDB could not finish the write yet ({message}, code {code}); will retry.")
        lowered = message.lower()
        if code == 18 or "authentication" in lowered or "bad auth" in lowered:  # Atlas: "bad auth", code 8000
            return SyncError(f"MongoDB refused the login ({message}): check the user name and password in MONGODB_URI "
                             "(in the password, + must be written %2B and % as %25), restart the backend, then retry the "
                             "failed records.", retry=False)
        if code == 13 or "not authorized" in lowered or "not allowed" in lowered:
            return SyncError(f"The MongoDB user may not write to the '{config.MONGODB_DB}' database ({message}): give "
                             f"it the readWrite role on {config.MONGODB_DB}.", retry=False)
        return SyncError(f"MongoDB refused the record ({message}, code {code}).", retry=False)
    if isinstance(exc, errors.ConfigurationError):  # InvalidURI too
        return SyncError(f"MONGODB_URI cannot be used ({kind}: {_safe(str(exc))[:200]}).", retry=False)
    if isinstance(exc, errors.InvalidName):
        return SyncError(f"MONGODB_DB is not a valid MongoDB database name ({_safe(str(exc))[:200]}).", retry=False)
    if isinstance(exc, (InvalidDocument, OverflowError, TypeError, ValueError)):
        return SyncError(f"MongoDB cannot store this record ({kind}).", retry=False)
    return SyncError(f"The write to MongoDB was interrupted ({kind}); will retry.")


def _database():
    """MONGODB_DB on the process's client.

    pymongo is imported here, by the first write: it adds most of a second to startup, which a backend without
    MONGODB_URI should not pay.
    """
    global _client
    import pymongo

    with _client_lock:
        if _client is None:
            _client = pymongo.MongoClient(config.MONGODB_URI, **_CLIENT_OPTIONS)
        return _client[config.MONGODB_DB]


# --- What is copied ----------------------------------------------------------------------


def _upload_document(dataset_id: int) -> dict | None:
    """The upload as copied to MongoDB, from SQLite as it is now; None once it is deleted."""
    dataset = database.get_dataset(dataset_id)
    if dataset is None:
        return None
    sheets = []
    for sheet in dataset["sheets"]:
        profile = dict(sheet["profile"])
        notes = profile.pop("user_notes", None)
        # mapping as saved: None when the sheet was never set up (the reports use the roles detected), {} when every
        # role was cleared; effective_mapping is what the reports use.
        setup = {"mapping": profile.pop("mapping", None), "effective_mapping": reports.effective_mapping(sheet["profile"]),
                 "classification": profile.pop("classification", None) or {}}
        sheets.append({"sheet_name": sheet["sheet_name"], "table_name": sheet["table_name"],
                       "row_count": sheet["row_count"], "profile": profile, "notes": notes, "setup": setup})
    copy = cloud.status_of(dataset_id)
    return {"_id": dataset_id, "filename": dataset["filename"], "size_bytes": dataset["size_bytes"],
            "uploaded_at": dataset["uploaded_at"], "register": dataset.get("register") or "unsorted", "sheets": sheets,
            "cloud": {k: copy[k] for k in ("status", "bucket", "path", "updated_at")} if copy else None}


def _target() -> str:
    """Where records go: the hosts and the database, never the user name or password. It is part of every fingerprint,
    so after a change of MONGODB_DB or cluster every record counts as not sent."""
    return f"{config.mongodb_hosts(config.MONGODB_URI)}/{config.MONGODB_DB}"


def _upload_fingerprint(document: dict | None) -> str:
    if document is None:
        return GONE
    state = json.dumps([_target(), document], sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(state.encode()).hexdigest()


def _chat_fingerprint(updated: int | float | None, deleted: bool) -> str:
    """A conversation's content changes only together with a larger "updated" (the server keeps the newer copy), so
    that time stands for it: the fingerprint needs no conversation read."""
    if updated is None or deleted:
        return GONE
    return hashlib.sha256(f"chat {_target()} {updated!r}".encode()).hexdigest()


def _record(kind: str, key: str) -> tuple[object, dict | None, str]:
    """(MongoDB _id, the document as it should be now or None to delete it, its fingerprint)."""
    if kind == "upload":
        document = _upload_document(int(key))
        return int(key), document, _upload_fingerprint(document)
    scope, _, chat_id = key.partition("/")
    with database.engine.connect() as conn:
        row = conn.execute(select(database.chats).where((database.chats.c.scope == scope)
                                                        & (database.chats.c.chat_id == chat_id))).mappings().first()
    if row is None or row["deleted"]:
        return key, None, GONE
    chat = json.loads(row["data"])
    document = {"_id": key, "scope": scope, "chat_id": chat_id, "title": chat.get("title", ""), "updated": row["updated"],
                "dataset_ids": chat.get("datasetIds", []), "documents": chat.get("documents", []),
                "turns": chat.get("turns", [])}
    return key, document, _chat_fingerprint(row["updated"], False)


def _send(kind: str, key: str) -> str:
    """Write the record's current state to MongoDB, or delete it there once it is gone; returns its fingerprint."""
    record_id, document, fingerprint = _record(kind, key)
    try:
        collection = _database()[_COLLECTIONS[kind]]
        if document is None:
            collection.delete_one({"_id": record_id})
        else:
            collection.replace_one({"_id": record_id}, {**document, "synced_at": _now()}, upsert=True)
    except Exception as exc:  # noqa: BLE001 - every driver error is classified, none is shown raw
        raise _sync_error(exc) from None
    return fingerprint


# --- The queue ---------------------------------------------------------------------------


def _write(statement, rows: list[dict] | None = None) -> int:
    """A write that waits out another writer (an upload storing a big sheet) instead of failing on 'database is locked'.
    Returns the number of rows it changed."""
    for pause in (0.5, 1, 2, 4, 8):
        try:
            with database.engine.begin() as conn:
                return conn.execute(statement, rows).rowcount
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            time.sleep(pause)
    with database.engine.begin() as conn:
        return conn.execute(statement, rows).rowcount


def _set(kind: str, key: str, **values) -> None:
    _write(update(mongo_sync).where((mongo_sync.c.kind == kind) & (mongo_sync.c.key == key)).values(updated_at=_now(), **values))


def _mark_pending(records: list[tuple[str, str]]) -> None:
    if not records:
        return
    statement = upsert(mongo_sync)
    statement = statement.on_conflict_do_update(
        index_elements=[mongo_sync.c.kind, mongo_sync.c.key],
        set_={"status": "pending", "attempts": 0, "error": None, "updated_at": statement.excluded.updated_at})
    now = _now()
    _write(statement, [{"kind": kind, "key": key, "status": "pending", "attempts": 0, "error": None, "synced_hash": None,
                        "updated_at": now} for kind, key in records])


def _write_marks() -> None:
    """Write the records marked in memory to mongo_sync as waiting."""
    with _marks_lock:
        records = sorted(_marked)
        _marked.clear()
    try:
        _mark_pending(records)
    except Exception:
        with _marks_lock:
            _marked.update(records)  # written on the next round
        raise


def touch(kind: str, key) -> None:
    """A record changed: an upload saved, edited or deleted ("upload", its id), or a conversation saved or deleted
    ("chat", "<scope>/<id>"). Only memory is touched, so the request is never slowed or failed by it."""
    if not configured():
        return
    try:
        with _marks_lock:
            _marked.add((kind, str(key)))
        if _worker is None:
            start()
        _wake.set()
    except Exception:  # noqa: BLE001 - a missed mark is caught by the next pass over every record
        pass


def _missing(synced: dict) -> set[tuple[str, str]]:
    """Records MongoDB confirmed but no longer holds (a collection emptied or dropped in Atlas). Empty when MongoDB
    cannot be read now: sending says why, and the next pass looks again."""
    sent: dict[str, set[str]] = {}
    for (kind, key), (status, fingerprint) in synced.items():
        if status == "done" and fingerprint != GONE:
            sent.setdefault(kind, set()).add(key)
    try:
        held = {kind: {str(doc["_id"]) for doc in _database()[_COLLECTIONS[kind]].find({}, {"_id": True})}
                for kind in sent}
    except Exception:  # noqa: BLE001 - unreachable, or no permission to read: the sends report it
        return set()
    return {(kind, key) for kind, keys in sent.items() for key in keys - held[kind]}


def reconcile(startup: bool = False) -> int:
    """Queue every record whose state differs from what MongoDB last confirmed, or that MongoDB no longer holds:
    records made before MongoDB was set up, a change no hook reported, a Supabase copy that moved on, a record deleted
    meanwhile, a new MONGODB_DB or cluster, a collection emptied in Atlas. At startup failed records get one more try
    too, so fixing backend/.env and restarting is enough. Returns how many were queued."""
    with database.engine.connect() as conn:
        synced = {(kind, key): (status, sent) for kind, key, status, sent in conn.execute(
            select(mongo_sync.c.kind, mongo_sync.c.key, mongo_sync.c.status, mongo_sync.c.synced_hash))}
        upload_ids = conn.execute(select(database.datasets.c.id)).scalars().all()
        chats = conn.execute(select(database.chats.c.scope, database.chats.c.chat_id, database.chats.c.updated,
                                    database.chats.c.deleted)).all()
    states = {("upload", str(dataset_id)): _upload_fingerprint(_upload_document(dataset_id)) for dataset_id in upload_ids}
    states.update({("chat", f"{scope}/{chat_id}"): _chat_fingerprint(updated, deleted)
                   for scope, chat_id, updated, deleted in chats})
    for record in synced:
        states.setdefault(record, GONE)  # deleted here since
    missing = _missing(synced)
    stale = []
    for record, fingerprint in states.items():
        status, sent = synced.get(record, (None, None))
        if status is None:
            changed = fingerprint != GONE  # a conversation deleted before it was ever sent: nothing to delete
        elif status == "done":
            changed = fingerprint != sent or (fingerprint != GONE and record in missing)
        else:
            changed = status == "failed" and startup
        if changed:
            stale.append(record)
    _mark_pending(stale)
    return len(stale)


def _send_pending() -> None:
    """Send every waiting record. Raises SyncError when MongoDB cannot be reached: the rest wait for the next round."""
    with database.engine.connect() as conn:
        waiting = conn.execute(select(mongo_sync.c.kind, mongo_sync.c.key, mongo_sync.c.attempts)
                               .where(mongo_sync.c.status == "pending").order_by(mongo_sync.c.updated_at)).all()
    for kind, key, attempts in waiting:
        try:
            fingerprint = _send(kind, key)
        except SyncError as exc:
            _set(kind, key, status="pending" if exc.retry else "failed", attempts=attempts + 1, error=str(exc))
            if exc.retry:
                raise
            continue
        except Exception as exc:  # noqa: BLE001 - e.g. the database busy; no raw text, which could hold SQL
            _set(kind, key, status="pending", attempts=attempts + 1, error=f"Unexpected error ({type(exc).__name__}); will retry.")
            continue
        _set(kind, key, status="done", attempts=attempts + 1, error=None, synced_hash=fingerprint)


def _pause(seconds: float, backing_off: bool) -> None:
    """Wait until a record is marked or ``seconds`` pass. After a passing failure a mark is only written down (sent when
    the pause ends), unless failed records were queued again by hand."""
    deadline = time.monotonic() + seconds
    while True:
        left = deadline - time.monotonic()
        if left <= 0 or not _wake.wait(left):
            return
        _wake.clear()
        if not backing_off or _hurry.is_set():
            _hurry.clear()
            return
        try:
            _write_marks()
        except Exception:  # noqa: BLE001 - kept in memory and written after the pause
            pass


def _run_forever() -> None:
    failures = 0
    startup = True
    next_pass = 0.0  # the first pass over every record runs at once
    while True:
        try:
            _write_marks()
            if time.monotonic() >= next_pass:
                reconcile(startup)
                startup = False
                next_pass = time.monotonic() + _SWEEP_SECONDS
            _send_pending()
            failures = 0
        except Exception:  # noqa: BLE001 - MongoDB unreachable, or the database busy or read-only: never stop
            failures += 1
        _pause(_BACKOFF[min(failures, len(_BACKOFF)) - 1] if failures else _SWEEP_SECONDS, failures > 0)


def start() -> bool:
    """Start the background sender (at startup; nothing happens without MONGODB_URI). Its first round compares every
    record with MongoDB's copy. Returns whether it runs."""
    global _worker
    if not configured():
        return False
    with _marks_lock:
        if _worker is None or not _worker.is_alive():
            # A daemon thread: a write waiting to be retried must never hold up a restart; it is sent after the start.
            _worker = threading.Thread(target=_run_forever, name="mongo-sync", daemon=True)
            _worker.start()
    return True


def retry_failed() -> int:
    """Queue every failed record again (e.g. after fixing the password or the user's role and restarting)."""
    if not configured():
        return 0
    count = _write(update(mongo_sync).where(mongo_sync.c.status == "failed")
                   .values(status="pending", attempts=0, updated_at=_now()))
    start()
    _hurry.set()
    _wake.set()
    return count


def summary() -> dict:
    counts = {"pending": 0, "done": 0, "failed": 0}
    last_error = None
    try:
        with database.engine.connect() as conn:
            for status, count in conn.execute(select(mongo_sync.c.status, func.count()).group_by(mongo_sync.c.status)):
                counts[status] = count
            last_error = conn.execute(select(mongo_sync.c.error).where((mongo_sync.c.status != "done")
                                                                         & mongo_sync.c.error.is_not(None))
                                      .order_by(mongo_sync.c.updated_at.desc()).limit(1)).scalar()
    except OperationalError as exc:
        if "no such table" not in str(exc):  # not created at startup (a read-only data folder): nothing to report
            raise
    on = configured()
    return {"configured": on, "hosts": _hosts().split(", ") if on else [], "database": config.MONGODB_DB if on else None,
            **counts, "last_error": last_error}
