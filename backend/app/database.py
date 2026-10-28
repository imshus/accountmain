"""PostgreSQL storage (Supabase) through SQLAlchemy: the one store of the uploads, books and chats. Nothing is kept on
this machine's disk; every read goes to the database (the in-process caches are keyed by data versions).

All tables live in their own schema (config.DATABASE_SCHEMA, set as each connection's search_path), which Supabase's web
API does not expose. Every uploaded sheet becomes its own table (``ds<id>_<sheet>``) with an explicit ``_rowid`` column
(1, 2, 3... in the sheet's order, as SQLite's rowid was). Two registry tables record which tables belong to which upload,
plus the statistics computed at upload time.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
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
    inspect,
    null,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.exc import DBAPIError

from . import config

# Without DATABASE_URL the engine points nowhere: every request then fails with storage_problem()'s message, and the
# app still starts so /api/health can say what to set.
engine = create_engine(
    config.DATABASE_URL or "postgresql+psycopg://database-url-not-set.invalid/none",
    pool_pre_ping=True,  # a connection the pooler or the network dropped is replaced, not handed out
    pool_recycle=300,
    pool_size=config.DATABASE_POOL_SIZE,
    max_overflow=config.DATABASE_POOL_SIZE,
    pool_timeout=30,
    connect_args={"connect_timeout": 10, "application_name": "accounts-ai"},
)


@event.listens_for(engine, "connect")
def _session_settings(dbapi_connection, _record):
    """Every connection works in the app's schema, in UTC. Set once per connection (the session pooler keeps it)."""
    with dbapi_connection.cursor() as cur:
        try:
            cur.execute("SET TIME ZONE 'UTC'")
        except Exception:  # noqa: BLE001 - a server without time zone names (some local builds): a zero offset is UTC
            dbapi_connection.rollback()
            cur.execute("SET TIME ZONE 0")
        cur.execute(f"SET search_path TO {quote_ident(config.DATABASE_SCHEMA)}, public")
    dbapi_connection.commit()


metadata = MetaData()

datasets = Table(
    "datasets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),  # from the dataset_ids sequence
    Column("filename", Text, nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    # The register the upload is filed under, which is also its copy's folder in Supabase: "sales" | "purchases" |
    # "unsorted" (NULL for uploads made before this was kept). register_added: a sheet of it was added to the books as
    # that register, so it stays filed there (an upload with both registers stays under the first one added).
    Column("register", String(20)),
    Column("register_added", Boolean),
)

dataset_sheets = Table(
    "dataset_sheets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dataset_id", Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("sheet_name", Text, nullable=False),
    Column("table_name", String(255), nullable=False, unique=True),
    Column("row_count", Integer, nullable=False),
    Column("profile_json", Text, nullable=False),
)

# A "books" set pairs sales-register sheets with purchase-register sheets (from one or more
# uploads) so they can be compared and combined: margins, net GST, party ledgers...
books = Table(
    "books",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),  # from the book_ids sequence
    Column("name", Text, nullable=False),
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

# Upload and set ids come from sequences, which never hand out a number twice (a deleted upload's id, and so its table
# names, cached tables, answers and "already imported" marks, can never be reused by a new upload; the same for set ids
# and their conversations, "book-<id>").
_SEQUENCES = {"dataset_ids": "datasets", "book_ids": "books"}

# Chat conversations as the app stores them, per scope ("home", "ds-<upload id>" or "book-<set id>"), so every device
# sees the same history. A deleted conversation stays as a tombstone (deleted, no data), so a device that still has
# it drops it instead of sending it back.
chats = Table(
    "chats",
    metadata,
    Column("scope", String(40), primary_key=True),
    Column("chat_id", String(64), primary_key=True),
    Column("updated", BigInteger, nullable=False),  # ms since epoch, set by the app on every change
    Column("deleted", Boolean, nullable=False),
    Column("data", Text),  # the conversation's JSON; NULL for a tombstone
    Index("ix_chats_scope_live_updated", "scope", "deleted", "updated"),
)


# Audit trail guarantees enforced by the database itself (Companies (Accounts) Rules, Rule 3(1)):
# the log can only grow, and vouchers can be cancelled but never deleted.
_FORBID_FUNCTION = ("CREATE OR REPLACE FUNCTION books_forbid() RETURNS trigger LANGUAGE plpgsql AS "
                    "$$ BEGIN RAISE EXCEPTION '%%', TG_ARGV[0] USING ERRCODE = 'integrity_constraint_violation'; END $$")  # %% : the driver's escape
_TRIGGERS = [  # (table, trigger name, event, message)
    ("audit_log", "audit_log_no_update", "UPDATE", "The audit log cannot be changed."),
    ("audit_log", "audit_log_no_delete", "DELETE", "The audit log cannot be deleted."),
    ("vouchers", "vouchers_no_delete", "DELETE", "Vouchers cannot be deleted; cancel them instead."),
]


def storage_problem() -> str | None:
    """Why this process cannot read or save, or None: no DATABASE_URL, a transaction-mode pooler address, or a database
    that cannot be reached or written. The message names only the host, never the address or password."""
    if not config.DATABASE_URL:
        return ("The backend has no database: set DATABASE_URL in backend/.env to the Supabase database's connection "
                "string (Supabase > Connect > Session pooler, port 5432) and restart the backend.")
    host = config.database_host()
    if host.endswith(":6543"):
        return (f"DATABASE_URL points at Supabase's transaction pooler ({host}). Use the Session pooler address "
                "(port 5432) instead: the app keeps its schema setting per connection.")
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET LOCAL statement_timeout = 5000")
            if conn.exec_driver_sql("SELECT current_setting('transaction_read_only')").scalar() == "on":
                return f"The database at {host} is read-only for the backend's user; it cannot save."
    except DBAPIError as exc:
        reason = _safe_reason(exc)
        return f"The backend cannot reach its database at {host}: {reason}"
    return None


def _safe_reason(exc: DBAPIError) -> str:
    """A database error's first line without the connection address or password."""
    message = str(getattr(exc, "orig", exc)).strip().splitlines()[0] if str(getattr(exc, "orig", exc)).strip() else type(exc).__name__
    if config.DATABASE_URL:
        authority = config.DATABASE_URL.partition("://")[2].partition("/")[0]
        password = authority.rpartition("@")[0].partition(":")[2]
        for secret in (config.DATABASE_URL, authority, password):
            if secret and len(secret) >= 4:
                message = message.replace(secret, "***")
    return re.sub(r"(postgres(?:ql)?(?:\+\w+)?://)[^\s/]*@", r"\1***@", message)[:300]


# Columns of this version that the database lacks, by table: always empty on Postgres (init_db adds them); kept so
# callers can keep reading whole rows through columns_of.
missing_columns: dict[str, set[str]] = {}


def columns_of(table: Table) -> dict:
    """Name -> the table's column, or NULL under that name for one the database lacks (missing_columns)."""
    missing = missing_columns.get(table.name, set())
    return {c.name: null().label(c.name) if c.name in missing else c for c in table.c}


def _add_new_columns(conn) -> None:
    """create_all makes missing tables but never changes existing ones: add the nullable columns that a table made by an
    older version lacks (its rows get NULL). Nothing to do once they are there."""
    have: dict[str, set[str]] = {}
    for name, column in conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = :schema"),
            {"schema": config.DATABASE_SCHEMA}):
        have.setdefault(name, set()).add(column)
    for table in metadata.sorted_tables:
        if table.name not in have:
            continue  # create_all makes it whole
        for column in table.columns:
            if column.name not in have[table.name] and column.nullable and not column.primary_key:
                conn.exec_driver_sql(f"ALTER TABLE {quote_ident(table.name)} ADD COLUMN IF NOT EXISTS "
                                     f"{quote_ident(column.name)} {column.type.compile(dialect=conn.dialect)}")


def app_tables(conn) -> set[str]:
    """Every table in the app's schema (registry, books and the uploads' sheet tables)."""
    return set(conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
                            {"schema": config.DATABASE_SCHEMA}).scalars())


def init_db() -> None:
    """Make the schema, tables, columns, sequences and audit triggers this version needs. One transaction under an
    advisory lock, so two backends starting together do not race (Postgres DDL is transactional)."""
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('accountsai-init'))"))
        conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(config.DATABASE_SCHEMA)}")
        conn.exec_driver_sql(f"SET LOCAL search_path TO {quote_ident(config.DATABASE_SCHEMA)}, public")
        _add_new_columns(conn)
        metadata.create_all(conn)
        tables = app_tables(conn)
        conn.exec_driver_sql(_FORBID_FUNCTION)
        for table, name, action, message in _TRIGGERS:
            if table in tables:
                conn.exec_driver_sql(
                    f"CREATE OR REPLACE TRIGGER {name} BEFORE {action} ON {quote_ident(table)} FOR EACH ROW "
                    f"EXECUTE FUNCTION books_forbid('{message}')")
        for sequence, table in _SEQUENCES.items():
            conn.exec_driver_sql(f"CREATE SEQUENCE IF NOT EXISTS {sequence}")
            highest = _highest_dataset_id(conn, tables) if table == "datasets" else _highest_book_id(conn)
            _raise_sequence(conn, sequence, highest)


def _raise_sequence(conn, sequence: str, highest: int) -> None:
    """Make the sequence's next number larger than ``highest`` (an id in use or still referred to)."""
    last, called = conn.exec_driver_sql(f"SELECT last_value, is_called FROM {sequence}").one()
    used = last if called else last - 1
    if highest > used:
        conn.execute(text("SELECT setval(:sequence, :value, true)"), {"sequence": sequence, "value": highest})


# Places that still name an upload's tables (ds<id>_...) after the upload itself is deleted.
_TABLE_REFERENCES = [("dataset_sheets", "table_name"), ("book_sheets", "table_name"), ("vouchers", "source"), ("bank_lines", "source"),
                     ("register_imports", "table_name")]


def _highest_dataset_id(conn, tables: set[str] | None = None) -> int:
    """The largest upload id in use or still referred to (by a sheet table's name, a set, a voucher's source...)."""
    tables = app_tables(conn) if tables is None else tables
    highest = conn.exec_driver_sql("SELECT COALESCE(MAX(id), 0) FROM datasets").scalar()
    names = [t for t in tables if t.startswith("ds")]
    for table, column in _TABLE_REFERENCES:
        if table in tables:
            names += conn.exec_driver_sql(
                f"SELECT DISTINCT {quote_ident(column)} FROM {quote_ident(table)} WHERE {quote_ident(column)} LIKE '%%ds%%'"
            ).scalars()
    for name in names:
        found = re.match(r"(?:\w+:)?ds(\d+)_", name or "")
        if found:
            highest = max(highest, int(found.group(1)))
    return highest


def _highest_book_id(conn) -> int:
    """The largest set id in use or named by a conversation ("book-<id>")."""
    scopes = conn.execute(select(chats.c.scope).where(chats.c.scope.like("book-%")).distinct()).scalars()
    highest = conn.exec_driver_sql("SELECT COALESCE(MAX(id), 0) FROM books").scalar()
    return max([highest, *(int(scope[5:]) for scope in scopes if scope[5:].isdigit())])


def _next_dataset_id(conn) -> int:
    """A new upload id, never one used before (no lock: a sequence)."""
    return int(conn.exec_driver_sql("SELECT nextval('dataset_ids')").scalar())


def _next_book_id(conn) -> int:
    """A new set id, never one used before."""
    return int(conn.exec_driver_sql("SELECT nextval('book_ids')").scalar())


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _slug(text_: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", text_.lower()).strip("_")[:40] or "sheet"


ROWID = "_rowid"  # each sheet table's row number: 1, 2, 3... in the sheet's order (editing.ROWID is the same name)


def _frame_for_sql(frame: pd.DataFrame) -> pd.DataFrame:
    """Store dates as ISO text (as before: the app reads them back by the profile's column kinds)."""
    out = frame.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            values = out[col]
            date_only = bool(((values.dt.normalize() == values) | values.isna()).all())
            out[col] = values.dt.strftime("%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M:%S")
    return out


def _sheet_column_type(series: pd.Series):
    """The SQL type of a sheet column: whole numbers as BIGINT, other numbers as DOUBLE PRECISION, true/false as
    BOOLEAN, everything else (text, and dates as ISO text) as TEXT."""
    if pd.api.types.is_bool_dtype(series):
        return Boolean
    if pd.api.types.is_integer_dtype(series):
        return BigInteger
    if pd.api.types.is_numeric_dtype(series):
        return Float(53)
    return Text


def _cell(value):
    """A frame value as the database driver takes it: NaN / NaT / pd.NA -> NULL, numpy numbers -> Python."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):  # a list or other non-scalar: kept as it is
        return value
    return value.item() if hasattr(value, "item") else value


def create_sheet_table(conn, table_name: str, frame: pd.DataFrame) -> None:
    """Make the sheet's table (an explicit "_rowid" identity column, then the sheet's columns) and load its rows in
    order with COPY, so "_rowid" is 1..n as SQLite's rowid was."""
    sql_frame = _frame_for_sql(frame)
    table = Table(table_name, MetaData(),
                  Column(ROWID, BigInteger, Identity(always=False, start=1), primary_key=True),
                  *(Column(str(name), _sheet_column_type(sql_frame[name])) for name in sql_frame.columns))
    table.create(conn)
    if sql_frame.empty:
        return
    columns = ", ".join(quote_ident(str(c)) for c in sql_frame.columns)
    raw = conn.connection.driver_connection  # psycopg: the same transaction as conn
    with raw.cursor() as cur:
        with cur.copy(f"COPY {quote_ident(table_name)} ({columns}) FROM STDIN") as copy:
            for row in sql_frame.itertuples(index=False, name=None):
                copy.write_row([_cell(v) for v in row])


def save_dataset(filename: str, size_bytes: int, sheets: list[tuple[str, pd.DataFrame, dict]],
                 register: str | None = None) -> int:
    """Write each (sheet name, frame, profile) to its own table and register the upload, filed under ``register``."""
    with engine.begin() as conn:
        dataset_id = _next_dataset_id(conn)
        conn.execute(
            insert(datasets).values(
                id=dataset_id,
                filename=filename,
                size_bytes=size_bytes,
                uploaded_at=datetime.now(timezone.utc),
                **({"register": register} if register else {}),
            )
        )

        used: set[str] = set()
        for position, (sheet_name, frame, profile) in enumerate(sheets):
            base = f"ds{dataset_id}_{_slug(sheet_name)}"
            table_name, n = base, 2
            while table_name in used:
                table_name, n = f"{base}_{n}", n + 1
            used.add(table_name)

            create_sheet_table(conn, table_name, frame)
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
    """uploaded_at is always UTC (naive values from older stores are taken as UTC)."""
    data = dict(row)
    if data["uploaded_at"].tzinfo is None:
        data["uploaded_at"] = data["uploaded_at"].replace(tzinfo=timezone.utc)
    return data


def list_datasets() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(*columns_of(datasets).values()).order_by(datasets.c.id.desc())).mappings().all()
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
        row = conn.execute(select(*columns_of(datasets).values()).where(datasets.c.id == dataset_id)).mappings().first()
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
        if registers:
            conn.execute(insert(book_sheets), [{"book_id": book_id, "table_name": t, "register": r} for t, r in registers])
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
    with engine.begin() as conn:
        # Read the sheets under the upload's row lock, so a delete racing another request sees one state.
        if conn.execute(select(datasets.c.id).where(datasets.c.id == dataset_id).with_for_update()).first() is None:
            return False
        names = conn.execute(select(dataset_sheets.c.table_name).where(dataset_sheets.c.dataset_id == dataset_id)).scalars().all()
        for name in names:
            conn.exec_driver_sql(f"DROP TABLE IF EXISTS {quote_ident(name)}")
        conn.execute(delete(dataset_sheets).where(dataset_sheets.c.dataset_id == dataset_id))
        conn.execute(delete(datasets).where(datasets.c.id == dataset_id))
    from .duck import forget  # duck imports this module

    forget(names)  # its prepared tables free their memory now
    return True


def read_preview(table_name: str, limit: int) -> pd.DataFrame:
    """The sheet's first ``limit`` rows in sheet order, without the row-number column."""
    with engine.connect() as conn:
        frame = pd.read_sql_query(
            f"SELECT * FROM {quote_ident(table_name)} ORDER BY {quote_ident(ROWID)} LIMIT {int(limit)}", conn)
    return frame.drop(columns=[ROWID], errors="ignore")


# --- Chat history ------------------------------------------------------------------------


# At most this many deletions (the newest) go out with a scope's list, so the list stays bounded. All of them stay
# stored: a device still holding an older one is answered with its deletion when it sends that conversation.
MAX_TOMBSTONES = 500


def _lock_scope(conn, scope: str) -> None:
    """Saves, trims and deletes of one scope take turns (Postgres lets writers run side by side; SQLite did not)."""
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"chats:{scope}"})


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
        kept = conn.execute(select(chats.c.data).where(live)
                            .order_by(chats.c.updated.desc(), chats.c.chat_id.collate("C")).limit(limit)).scalars().all()
        gone = conn.execute(select(chats.c.chat_id, chats.c.updated).where((chats.c.scope == scope) & chats.c.deleted)
                            .order_by(chats.c.updated.desc()).limit(MAX_TOMBSTONES)).all()
    return [json.loads(data) for data in kept], [{"id": chat_id, "updated": updated} for chat_id, updated in gone]


def trim_chats(scope: str, keep: int) -> list[tuple[str, int | float]]:
    """Turn every conversation of the scope but the ``keep`` newest into a tombstone at its own time (a device that
    still has that copy drops it; a later edit revives it). Returns their (id, updated)."""
    live = (chats.c.scope == scope) & ~chats.c.deleted
    newest = select(chats.c.chat_id).where(live).order_by(chats.c.updated.desc(), chats.c.chat_id.collate("C")).limit(keep)
    with engine.begin() as conn:  # under the scope's lock: a conversation saved meanwhile is never the one dropped
        _lock_scope(conn, scope)
        return [tuple(row) for row in conn.execute(update(chats).where(live & chats.c.chat_id.not_in(newest))
                                                   .values(deleted=True, data=None)
                                                   .returning(chats.c.chat_id, chats.c.updated))]


def delete_scope_chats(scope: str) -> list[str]:
    """Delete every conversation of a scope whose upload or set was deleted: each becomes a tombstone at now (or at its
    own time, should a device's clock be ahead), so a device that still has it drops it. Returns their ids."""
    now = int(time.time() * 1000)
    with engine.begin() as conn:
        _lock_scope(conn, scope)
        return conn.execute(update(chats).where((chats.c.scope == scope) & ~chats.c.deleted)
                            .values(deleted=True, data=None, updated=func.greatest(chats.c.updated, now))
                            .returning(chats.c.chat_id)).scalars().all()


def _kept_chat(row) -> dict:
    if row["deleted"]:
        return {"chat": None, "deleted": {"id": row["chat_id"], "updated": row["updated"]}}
    return {"chat": json.loads(row["data"]), "deleted": None}


def _keep_newer(scope: str, chat_id: str, values: dict, wins) -> dict:
    """Store ``values`` only where ``wins`` (a comparison of the new row with the stored one) holds, and return what is
    kept. One statement decides and writes, under the scope's lock, so two devices saving at the same moment cannot
    lose the newer copy; the conflicting row stays locked to the end of the transaction, so the row read back is the
    one kept."""
    statement = upsert(chats).values(scope=scope, chat_id=chat_id, **values)
    statement = statement.on_conflict_do_update(
        index_elements=[chats.c.scope, chats.c.chat_id], set_=values, where=wins(statement.excluded))
    with engine.begin() as conn:
        _lock_scope(conn, scope)
        conn.execute(statement)
        row = conn.execute(select(chats).where((chats.c.scope == scope) & (chats.c.chat_id == chat_id))).mappings().one()
    return _kept_chat(row)


def _ms(updated: int | float) -> int:
    """A chat time as whole milliseconds (the column is BIGINT; a fraction is rounded up, so "newer" never flips)."""
    return int(math.ceil(updated))


def save_chat(scope: str, chat_id: str, updated: int | float, data: str) -> dict:
    """Keep the conversation (JSON ``data``) unless the stored copy or tombstone is as new or newer. Returns
    {"chat": the conversation kept, "deleted": None}, or {"chat": None, "deleted": {"id", "updated"}}."""
    return _keep_newer(scope, chat_id, {"updated": _ms(updated), "deleted": False, "data": data},
                       lambda new: new.updated > chats.c.updated)


def delete_chat(scope: str, chat_id: str, updated: int | float) -> dict:
    """Leave a tombstone at ``updated`` unless the stored conversation is newer."""
    return _keep_newer(scope, chat_id, {"updated": _ms(updated), "deleted": True, "data": None},
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


def _json_value(value):
    if isinstance(value, float):
        # Drop binary noise such as 342357.66000000003 so sums read exactly as the books do.
        return round(value, 8) if math.isfinite(value) else None
    if isinstance(value, bytes):
        return value.hex()
    if hasattr(value, "is_finite") and hasattr(value, "as_tuple"):  # Decimal
        return float(value) if value.is_finite() else None
    return value


_TABLE_NAME = re.compile(r'"((?:[^"]|"")+)"|\b(ds\d+_\w+)\b', re.IGNORECASE)


def run_select(sql: str, allowed_tables: set[str], limit: int = config.SQL_RESULT_LIMIT) -> QueryResult:
    """Run one SELECT the app built itself over ``allowed_tables`` (people's and the AI's queries run in DuckDB over
    copies: duck.Session). A read-only transaction with a time limit; any sheet table it names must be allowed."""
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise QueryError("The query is empty.")
    if ";" in statement:
        raise QueryError("Only one SELECT statement is allowed.")
    allowed = {t.lower() for t in allowed_tables}
    for quoted, bare in _TABLE_NAME.findall(statement):
        name = (quoted.replace('""', '"') or bare).lower()
        if name.startswith("ds") and re.match(r"ds\d+_", name) and name not in allowed:
            raise QueryError(f"Only this upload's tables can be queried ({name}).")

    started = time.monotonic()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(config.SQL_TIMEOUT_SECONDS * 1000)}")
            result = conn.exec_driver_sql(f"SELECT * FROM ({statement}) AS q LIMIT {int(limit) + 1}")
            columns = list(result.keys())
            fetched = result.fetchall()
            conn.rollback()
    except DBAPIError as exc:
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == "57014":
            raise QueryError(f"The query took longer than {config.SQL_TIMEOUT_SECONDS} seconds and was stopped.") from exc
        if sqlstate == "25006":
            raise QueryError("Only SELECT queries are allowed.") from exc
        raise QueryError(_safe_reason(exc)) from exc

    return QueryResult(
        columns=columns,
        rows=[[_json_value(v) for v in row] for row in fetched[:limit]],
        truncated=len(fetched) > limit,
        elapsed_ms=round((time.monotonic() - started) * 1000, 1),
    )


__all__ = ["ROWID", "QueryError", "QueryResult", "app_tables", "columns_of", "create_sheet_table", "engine", "init_db",
           "inspect", "metadata", "quote_ident", "run_select", "storage_problem", "upsert"]
