"""SQLite storage through SQLAlchemy.

Every uploaded sheet becomes its own table (``ds<id>_<sheet>``). Two registry tables
record which tables belong to which upload, plus the statistics computed at upload time.
User and LLM queries go through ``run_select``, which opens the database read-only and
uses SQLite's authorizer so a statement can only SELECT from the tables of one upload.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import (
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
    insert,
    select,
)
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
id_high_water = Table(
    "id_high_water",
    metadata,
    Column("name", String(50), primary_key=True),
    Column("value", Integer, nullable=False),
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
        book_id = conn.execute(
            insert(books).values(name=name, created_at=datetime.now(timezone.utc))
        ).inserted_primary_key[0]
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
