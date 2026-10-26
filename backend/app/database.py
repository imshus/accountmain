"""SQLite storage through SQLAlchemy.

Every uploaded sheet becomes its own table (``ds<id>_<sheet>``). Two registry tables
record which tables belong to which upload, plus the statistics computed at upload time.
User and LLM queries go through ``run_select``, which opens the database read-only and
uses SQLite's authorizer so a statement can only SELECT from the tables of one upload.
"""

from __future__ import annotations

import getpass
import json
import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    event,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.sqlite import insert as upsert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from . import config

engine = create_engine(f"sqlite:///{config.DB_PATH}")


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


def _connect_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"{config.DB_PATH.as_uri()}?mode=ro", uri=True, check_same_thread=False)
    if hasattr(sqlite3, "SQLITE_DBCONFIG_DQS_DML"):  # Python 3.12+
        # Without this, SQLite reads a misspelled "column" as the text 'column' and the
        # query quietly returns wrong numbers instead of failing.
        conn.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DML, False)
    return conn


readonly_engine = create_engine("sqlite://", creator=_connect_readonly, poolclass=NullPool)

metadata = MetaData()

datasets = Table(
    "datasets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("filename", String(255), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
)

dataset_sheets = Table(
    "dataset_sheets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dataset_id", Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("sheet_name", String(255), nullable=False),
    Column("table_name", String(255), nullable=False, unique=True),
    Column("row_count", Integer, nullable=False),
    Column("profile_json", Text, nullable=False),
)

# A "books" set pairs sales-register sheets with purchase-register sheets (from one or more
# uploads) so they can be compared and combined: margins, net GST, party ledgers...
books = Table(
    "books",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

book_sheets = Table(
    "book_sheets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("book_id", Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("table_name", String(255), nullable=False),
    Column("register", String(20), nullable=False),  # "sales" | "purchases" | "unused"
)

# The highest upload id ever handed out. SQLite reuses the largest id once that row is deleted, and a
# corrected re-upload would then get the deleted file's table names, so cached tables, cached answers,
# books and "already imported" voucher marks would all point at the new file as if it were the old one.
# The same for set ids ("books"): a new set must not get a deleted set's conversations ("book-<id>").
id_high_water = Table(
    "id_high_water",
    metadata,
    Column("name", String(50), primary_key=True),
    Column("value", Integer, nullable=False),
)

# Chat conversations as the app stores them, per scope ("home", "ds-<upload id>" or "book-<set id>"), so every device
# sees the same history. A deleted conversation stays as a tombstone (deleted, no data), so a device that still has
# it drops it instead of sending it back.
chats = Table(
    "chats",
    metadata,
    Column("scope", String(40), primary_key=True),
    Column("chat_id", String(64), primary_key=True),
    Column("updated", Integer, nullable=False),  # ms since epoch, set by the app on every change
    Column("deleted", Boolean, nullable=False),
    Column("data", Text),  # the conversation's JSON; NULL for a tombstone
)


# Audit trail guarantees enforced by the database itself (Companies (Accounts) Rules, Rule 3(1)):
# the log can only grow, and vouchers can be cancelled but never deleted.
_TRIGGERS = [
    "CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log "
    "BEGIN SELECT RAISE(ABORT, 'The audit log cannot be changed.'); END",
    "CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log "
    "BEGIN SELECT RAISE(ABORT, 'The audit log cannot be deleted.'); END",
    "CREATE TRIGGER IF NOT EXISTS vouchers_no_delete BEFORE DELETE ON vouchers "
    "BEGIN SELECT RAISE(ABORT, 'Vouchers cannot be deleted; cancel them instead.'); END",
]


def storage_problem() -> str | None:
    """Why this process cannot save, or None. A data folder or database file it may not write (typically made by a
    command run with sudo) makes SQLite fail every save with "attempt to write a readonly database"."""
    files = [config.DB_PATH.with_name(config.DB_PATH.name + suffix) for suffix in ("", "-wal", "-shm", "-journal")]
    for path in (config.DATA_DIR, *files):
        if path.exists() and not os.access(path, os.W_OK):
            try:
                user = getpass.getuser()
            except Exception:  # noqa: BLE001 - no user name in the environment
                user = "the backend's user"
            return (f"The server cannot save: {path} is read-only for the user running the backend ({user}). "
                    f"On the server run: sudo chown -R {user} {config.DATA_DIR}  and restart the backend.")
    return None


def init_db() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    metadata.create_all(engine)
    with engine.begin() as conn:
        tables = set(conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars())
        for trigger in _TRIGGERS:
            if trigger.split(" ON ")[1].split()[0] in tables:
                conn.exec_driver_sql(trigger)
        if conn.execute(select(id_high_water.c.value).where(id_high_water.c.name == "datasets")).first() is None:
            conn.execute(insert(id_high_water).values(name="datasets", value=_highest_dataset_id(conn)))
        if conn.execute(select(id_high_water.c.value).where(id_high_water.c.name == "books")).first() is None:
            conn.execute(insert(id_high_water).values(name="books", value=_highest_book_id(conn)))


# Places that still name an upload's tables (ds<id>_...) after the upload itself is deleted.
_TABLE_REFERENCES = [("dataset_sheets", "table_name"), ("book_sheets", "table_name"), ("vouchers", "source"), ("bank_lines", "source")]


def _highest_dataset_id(conn) -> int:
    """The largest upload id in use or still referred to; databases made before id_high_water start from it."""
    tables = set(conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars())
    highest = conn.exec_driver_sql("SELECT COALESCE(MAX(id), 0) FROM datasets").scalar()
    names = [t for t in tables if t.startswith("ds")]
    for table, column in _TABLE_REFERENCES:
        if table in tables:
            names += conn.exec_driver_sql(
                f"SELECT DISTINCT {quote_ident(column)} FROM {quote_ident(table)} WHERE {quote_ident(column)} LIKE '%ds%'"
            ).scalars()
    for name in names:
        found = re.match(r"(?:\w+:)?ds(\d+)_", name or "")
        if found:
            highest = max(highest, int(found.group(1)))
    return highest


def _next_dataset_id(conn) -> int:
    """A new upload id, never one used before (call inside the upload's transaction)."""
    # Also above any id already in the table, should an older copy of the app have added uploads.
    row = conn.exec_driver_sql(
        "UPDATE id_high_water SET value = max(value, (SELECT COALESCE(MAX(id), 0) FROM datasets)) + 1 "
        "WHERE name = 'datasets' RETURNING value"
    ).first()
    if row is not None:
        return row[0]
    value = _highest_dataset_id(conn) + 1
    conn.execute(insert(id_high_water).values(name="datasets", value=value))
    return value


def _highest_book_id(conn) -> int:
    """The largest set id in use or named by a conversation ("book-<id>"); databases made before sets were tracked in
    id_high_water start from it."""
    scopes = conn.execute(select(chats.c.scope).where(chats.c.scope.like("book-%")).distinct()).scalars()
    highest = conn.exec_driver_sql("SELECT COALESCE(MAX(id), 0) FROM books").scalar()
    return max([highest, *(int(scope[5:]) for scope in scopes if scope[5:].isdigit())])


def _next_book_id(conn) -> int:
    """A new set id, never one used before (call inside the transaction that adds the set)."""
    row = conn.exec_driver_sql(
        "UPDATE id_high_water SET value = max(value, (SELECT COALESCE(MAX(id), 0) FROM books)) + 1 "
        "WHERE name = 'books' RETURNING value"
    ).first()
    if row is not None:
        return row[0]
    value = _highest_book_id(conn) + 1
    conn.execute(insert(id_high_water).values(name="books", value=value))
    return value


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _slug(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", text.lower()).strip("_")[:40] or "sheet"


def _frame_for_sql(frame: pd.DataFrame) -> pd.DataFrame:
    """Store dates as ISO text so SQLite's date functions work on them."""
    out = frame.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            values = out[col]
            date_only = bool(((values.dt.normalize() == values) | values.isna()).all())
            out[col] = values.dt.strftime("%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M:%S")
    return out


def save_dataset(filename: str, size_bytes: int, sheets: list[tuple[str, pd.DataFrame, dict]]) -> int:
    """Write each (sheet name, frame, profile) to its own table and register the upload."""
    with engine.begin() as conn:
        dataset_id = _next_dataset_id(conn)
        conn.execute(
            insert(datasets).values(
                id=dataset_id,
                filename=filename,
                size_bytes=size_bytes,
                uploaded_at=datetime.now(timezone.utc),
            )
        )

        used: set[str] = set()
        for position, (sheet_name, frame, profile) in enumerate(sheets):
            base = f"ds{dataset_id}_{_slug(sheet_name)}"
            table_name, n = base, 2
            while table_name in used:
                table_name, n = f"{base}_{n}", n + 1
            used.add(table_name)

            _frame_for_sql(frame).to_sql(table_name, conn, index=False, if_exists="fail", chunksize=1000)
            conn.execute(
                insert(dataset_sheets).values(
                    dataset_id=dataset_id,
                    position=position,
                    sheet_name=sheet_name,
                    table_name=table_name,
                    row_count=len(frame),
                    profile_json=json.dumps(profile),
                )
            )
    return dataset_id


def _with_utc(row) -> dict:
    """SQLite drops the timezone; uploaded_at is always stored in UTC."""
    data = dict(row)
    if data["uploaded_at"].tzinfo is None:
        data["uploaded_at"] = data["uploaded_at"].replace(tzinfo=timezone.utc)
    return data


def list_datasets() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(datasets).order_by(datasets.c.id.desc())).mappings().all()
        sheets = conn.execute(select(dataset_sheets.c.dataset_id, dataset_sheets.c.row_count)).all()
    sheet_count: dict[int, int] = {}
    row_count: dict[int, int] = {}
    for dataset_id, rows_in_sheet in sheets:
        sheet_count[dataset_id] = sheet_count.get(dataset_id, 0) + 1
        row_count[dataset_id] = row_count.get(dataset_id, 0) + rows_in_sheet
    return [
        {
            **_with_utc(row),
            "sheet_count": sheet_count.get(row["id"], 0),
            "row_count": row_count.get(row["id"], 0),
        }
        for row in rows
    ]


def get_dataset(dataset_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(select(datasets).where(datasets.c.id == dataset_id)).mappings().first()
        if row is None:
            return None
        sheets = (
            conn.execute(
                select(dataset_sheets)
                .where(dataset_sheets.c.dataset_id == dataset_id)
                .order_by(dataset_sheets.c.position)
            )
            .mappings()
            .all()
        )
    return {
        **_with_utc(row),
        "sheets": [{**dict(s), "profile": _load_profile(s["profile_json"])} for s in sheets],
    }


def _load_profile(profile_json: str) -> dict:
    profile = json.loads(profile_json)
    if "checks" not in profile:  # uploads made before checks existed stored plain notes
        profile["checks"] = [{"level": "info", "message": note} for note in profile.pop("notes", [])]
    return profile


def create_book(name: str, registers: list[tuple[str, str]]) -> int:
    """registers: (table_name, "sales" | "purchases" | "unused") pairs."""
    with engine.begin() as conn:
        book_id = _next_book_id(conn)
        conn.execute(insert(books).values(id=book_id, name=name, created_at=datetime.now(timezone.utc)))
        for table_name, register in registers:
            conn.execute(insert(book_sheets).values(book_id=book_id, table_name=table_name, register=register))
    return book_id


def list_books() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(books).order_by(books.c.id.desc())).mappings().all()
        links = conn.execute(select(book_sheets.c.book_id, book_sheets.c.register)).all()
    counts: dict[int, dict[str, int]] = {}
    for book_id, register in links:
        counts.setdefault(book_id, {}).setdefault(register, 0)
        counts[book_id][register] += 1
    return [
        {**_with_time(row), "sales_sheets": counts.get(row["id"], {}).get("sales", 0),
         "purchase_sheets": counts.get(row["id"], {}).get("purchases", 0)}
        for row in rows
    ]


def get_book(book_id: int) -> dict | None:
    """The book with each linked sheet (profile included); sheets whose upload was deleted are skipped."""
    with engine.connect() as conn:
        row = conn.execute(select(books).where(books.c.id == book_id)).mappings().first()
        if row is None:
            return None
        links = conn.execute(
            select(
                book_sheets.c.table_name,
                book_sheets.c.register,
                dataset_sheets.c.dataset_id,
                dataset_sheets.c.sheet_name,
                dataset_sheets.c.row_count,
                dataset_sheets.c.profile_json,
                datasets.c.filename,
            )
            .join(dataset_sheets, dataset_sheets.c.table_name == book_sheets.c.table_name)
            .join(datasets, datasets.c.id == dataset_sheets.c.dataset_id)
            .where(book_sheets.c.book_id == book_id)
            .order_by(book_sheets.c.id)
        ).mappings().all()
    sheets = [
        {
            "dataset_id": link["dataset_id"],
            "filename": link["filename"],
            "sheet_name": link["sheet_name"],
            "table_name": link["table_name"],
            "row_count": link["row_count"],
            "register": link["register"],
            "profile": _load_profile(link["profile_json"]),
        }
        for link in links
    ]
    return {**_with_time(row), "sheets": sheets}


def set_book_registers(book_id: int, registers: dict[str, str]) -> None:
    with engine.begin() as conn:
        for table_name, register in registers.items():
            conn.execute(
                book_sheets.update()
                .where((book_sheets.c.book_id == book_id) & (book_sheets.c.table_name == table_name))
                .values(register=register)
            )


def delete_book(book_id: int) -> bool:
    with engine.begin() as conn:
        conn.execute(delete(book_sheets).where(book_sheets.c.book_id == book_id))
        return conn.execute(delete(books).where(books.c.id == book_id)).rowcount > 0


def _with_time(row) -> dict:
    data = dict(row)
    if data["created_at"].tzinfo is None:
        data["created_at"] = data["created_at"].replace(tzinfo=timezone.utc)
    return data


def delete_dataset(dataset_id: int) -> bool:
    dataset = get_dataset(dataset_id)
    if dataset is None:
        return False
    with engine.begin() as conn:
        for sheet in dataset["sheets"]:
            conn.exec_driver_sql(f"DROP TABLE IF EXISTS {quote_ident(sheet['table_name'])}")
        conn.execute(delete(dataset_sheets).where(dataset_sheets.c.dataset_id == dataset_id))
        conn.execute(delete(datasets).where(datasets.c.id == dataset_id))
    from .duck import forget  # duck imports this module

    forget(sheet["table_name"] for sheet in dataset["sheets"])  # its prepared tables free their memory now
    return True


def read_preview(table_name: str, limit: int) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(f"SELECT * FROM {quote_ident(table_name)} LIMIT {int(limit)}", conn)


# --- Chat history ------------------------------------------------------------------------


# At most this many deletions (the newest) go out with a scope's list, so the list stays bounded. All of them stay
# stored: a device still holding an older one is answered with its deletion when it sends that conversation.
MAX_TOMBSTONES = 500


def chat_scope_exists(scope: str) -> bool:
    """Whether the upload ("ds-<id>") or set ("book-<id>") a conversation belongs to still exists; "home" always does."""
    kind, _, number = scope.partition("-")
    table = {"ds": datasets, "book": books}.get(kind)
    if table is None:
        return True
    with engine.connect() as conn:
        return conn.execute(select(table.c.id).where(table.c.id == int(number))).first() is not None


def list_chats(scope: str, limit: int | None = None) -> tuple[list[dict], list[dict]]:
    """The scope's conversations (the ``limit`` newest, newest first) and its newest tombstones ({"id", "updated"})."""
    live = (chats.c.scope == scope) & ~chats.c.deleted
    with engine.connect() as conn:
        kept = conn.execute(select(chats.c.data).where(live).order_by(chats.c.updated.desc(), chats.c.chat_id)
                            .limit(limit)).scalars().all()
        gone = conn.execute(select(chats.c.chat_id, chats.c.updated).where((chats.c.scope == scope) & chats.c.deleted)
                            .order_by(chats.c.updated.desc()).limit(MAX_TOMBSTONES)).all()
    return [json.loads(data) for data in kept], [{"id": chat_id, "updated": updated} for chat_id, updated in gone]


def trim_chats(scope: str, keep: int) -> list[tuple[str, int | float]]:
    """Turn every conversation of the scope but the ``keep`` newest into a tombstone at its own time (a device that
    still has that copy drops it; a later edit revives it). Returns their (id, updated)."""
    live = (chats.c.scope == scope) & ~chats.c.deleted
    newest = select(chats.c.chat_id).where(live).order_by(chats.c.updated.desc(), chats.c.chat_id).limit(keep)
    with engine.begin() as conn:  # one statement: a conversation saved meanwhile is never the one dropped
        return [tuple(row) for row in conn.execute(update(chats).where(live & chats.c.chat_id.not_in(newest))
                                                   .values(deleted=True, data=None)
                                                   .returning(chats.c.chat_id, chats.c.updated))]


def delete_scope_chats(scope: str) -> list[str]:
    """Delete every conversation of a scope whose upload or set was deleted: each becomes a tombstone at now (or at its
    own time, should a device's clock be ahead), so a device that still has it drops it. Returns their ids."""
    now = int(time.time() * 1000)
    with engine.begin() as conn:
        return conn.execute(update(chats).where((chats.c.scope == scope) & ~chats.c.deleted)
                            .values(deleted=True, data=None, updated=func.max(chats.c.updated, now))
                            .returning(chats.c.chat_id)).scalars().all()


def _kept_chat(row) -> dict:
    if row["deleted"]:
        return {"chat": None, "deleted": {"id": row["chat_id"], "updated": row["updated"]}}
    return {"chat": json.loads(row["data"]), "deleted": None}


def _keep_newer(scope: str, chat_id: str, values: dict, wins) -> dict:
    """Store ``values`` only where ``wins`` (a comparison of the new row with the stored one) holds, and return what is
    kept. One statement decides and writes, so two devices saving at the same moment cannot lose the newer copy."""
    statement = upsert(chats).values(scope=scope, chat_id=chat_id, **values)
    statement = statement.on_conflict_do_update(
        index_elements=[chats.c.scope, chats.c.chat_id], set_=values, where=wins(statement.excluded))
    with engine.begin() as conn:
        conn.execute(statement)  # the transaction now holds the write lock, so the row read back is the one kept
        row = conn.execute(select(chats).where((chats.c.scope == scope) & (chats.c.chat_id == chat_id))).mappings().one()
    return _kept_chat(row)


def save_chat(scope: str, chat_id: str, updated: int | float, data: str) -> dict:
    """Keep the conversation (JSON ``data``) unless the stored copy or tombstone is as new or newer. Returns
    {"chat": the conversation kept, "deleted": None}, or {"chat": None, "deleted": {"id", "updated"}}."""
    return _keep_newer(scope, chat_id, {"updated": updated, "deleted": False, "data": data},
                       lambda new: new.updated > chats.c.updated)


def delete_chat(scope: str, chat_id: str, updated: int | float) -> dict:
    """Leave a tombstone at ``updated`` unless the stored conversation is newer."""
    return _keep_newer(scope, chat_id, {"updated": updated, "deleted": True, "data": None},
                       lambda new: new.updated >= chats.c.updated)


# --- Guarded read-only queries ---------------------------------------------------------


class QueryError(Exception):
    """A query was rejected or failed. The message is safe to show to the user."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    truncated: bool
    elapsed_ms: float

    def as_dict(self) -> dict:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": len(self.rows),
            "truncated": self.truncated,
            "elapsed_ms": self.elapsed_ms,
        }


_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


def _authorizer(allowed_tables: set[str]):
    allowed = {t.lower() for t in allowed_tables}

    def check(action, arg1, _arg2, _db_name, _trigger):
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if (arg1 or "").lower() in allowed else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY

    return check


def _json_value(value):
    if isinstance(value, float):
        # Drop binary noise such as 342357.66000000003 so sums read exactly as the books do.
        return round(value, 8) if math.isfinite(value) else None
    if isinstance(value, bytes):
        return value.hex()
    return value


def run_select(sql: str, allowed_tables: set[str], limit: int = config.SQL_RESULT_LIMIT) -> QueryResult:
    """Run one SELECT statement that may only read ``allowed_tables``."""
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise QueryError("The query is empty.")

    started = time.monotonic()
    deadline = started + config.SQL_TIMEOUT_SECONDS
    with readonly_engine.connect() as conn:
        raw = conn.connection.driver_connection
        raw.set_authorizer(_authorizer(allowed_tables))
        raw.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            result = conn.exec_driver_sql(statement)
            if not result.returns_rows:
                raise QueryError("Only SELECT queries are allowed.")
            columns = list(result.keys())
            fetched = result.fetchmany(limit + 1)
        except DBAPIError as exc:
            message = str(exc.orig)
            if "not authorized" in message:
                message = "Only SELECT queries on this upload's tables are allowed."
            elif "prohibited" in message:
                message = f"Only this upload's tables can be queried ({message})."
            elif "interrupted" in message:
                message = f"The query took longer than {config.SQL_TIMEOUT_SECONDS} seconds and was stopped."
            raise QueryError(message) from exc
        finally:
            raw.set_authorizer(None)
            raw.set_progress_handler(None, 0)

    return QueryResult(
        columns=columns,
        rows=[[_json_value(v) for v in row] for row in fetched[:limit]],
        truncated=len(fetched) > limit,
        elapsed_ms=round((time.monotonic() - started) * 1000, 1),
    )
