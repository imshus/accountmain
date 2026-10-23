"""DuckDB query engine over the uploaded sheets, with pandas preparing the data.

pandas loads each sheet (dates as datetimes, numbers cleaned) and DuckDB queries it through one view
per sheet, under the sheet's usual table name. Number columns become exact fixed-point DECIMALs with
just enough decimals for every value (2 for rupees, 3 for grams...), so SUM, AVG and comparisons are
exact to the last paisa or milligram; columns that need more than 4 decimals stay DOUBLE.

Every session is a private connection to one shared in-memory DuckDB whose file and network access is
switched off and whose configuration is locked at startup. A session's tables are TEMP views over
pandas frames registered on its own connection, so no other session can see them. Only single SELECT
statements are accepted, and each query is interrupted after SQL_TIMEOUT_SECONDS.

Preparing a sheet (reading it, cleaning types, finding each column's exact decimals) is done once and
kept in memory until the sheet changes, so opening a session only registers ready-made tables and
answers come back in milliseconds.
"""

import atexit
import hashlib
import json
import math
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import duckdb
import numpy as np
import pandas as pd

from . import config
from .database import QueryError, QueryResult, quote_ident
from .editing import ROWID, load_frame

MAX_SCALE = 4
_DECIMAL_LIMIT = 1e13  # DECIMAL(18, 4) holds up to 1e14; stay well inside it


def decimal_scale(values: pd.Series) -> int | None:
    """Fewest decimals (0-4) that represent every value exactly, or None when more are needed."""
    v = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype="float64")
    if v.size == 0:
        return 0
    if not np.isfinite(v).all() or np.abs(v).max() >= _DECIMAL_LIMIT:
        return None
    for scale in range(MAX_SCALE + 1):
        scaled = v * 10.0**scale
        # Allow only float noise (3.666 * 1000 = 3665.9999999999995), never a real fraction.
        if np.all(np.abs(scaled - np.rint(scaled)) <= np.maximum(1e-6, np.abs(scaled) * 1e-15)):
            return scale
    return None


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: str  # number | date | text
    scale: int | None = None  # decimals kept exactly (numbers); None = DOUBLE

    def as_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "kind": self.kind, "scale": self.scale}


def json_value(value):
    """A DuckDB result cell as plain JSON (exact decimals become int or float)."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _clean_error(exc: Exception) -> str:
    # Drop DuckDB's caret diagram and its suggestions of internal catalog tables.
    message = str(exc).strip().split("\nLINE ")[0].split("\nDid you mean")[0].strip()
    for prefix in ("Binder Error: ", "Parser Error: ", "Conversion Error: ", "Catalog Error: ", "Invalid Input Error: "):
        message = message.replace(prefix, "")
    return message[:600]


# --- prepared tables, kept between requests ---------------------------------------------------------

Prepared = tuple[pd.DataFrame, list[str], list["Field"]]  # cleaned frame, view SELECT list, fields
_PREPARED: OrderedDict[tuple, Prepared] = OrderedDict()
_PREPARED_MAX = 32
_LOCK = threading.Lock()


def sheet_key(sheet: dict) -> tuple:
    """Changes whenever the sheet's data changes: every edit rewrites its profile (row count, column stats)."""
    profile = json.dumps(sheet["profile"], sort_keys=True, default=str)
    return ("sheet", sheet["table_name"], sheet["row_count"], hashlib.sha1(profile.encode()).hexdigest())


def cached(key: tuple, build: Callable[[], object]):
    """Least-recently-used memory of prepared tables (and anything else keyed the same way)."""
    with _LOCK:
        if key in _PREPARED:
            _PREPARED.move_to_end(key)
            return _PREPARED[key]
    value = build()
    with _LOCK:
        _PREPARED[key] = value
        _PREPARED.move_to_end(key)
        while len(_PREPARED) > _PREPARED_MAX:
            _PREPARED.popitem(last=False)
    return value


def _sheet_tables(key) -> set[str]:
    """Table names of every sheet_key inside a cache key (registers and combined keys nest them)."""
    if not isinstance(key, tuple):
        return set()
    if len(key) >= 4 and key[0] == "sheet":  # a sheet_key, possibly with the register appended
        return {key[1]}
    return set().union(*(_sheet_tables(part) for part in key))


def forget(table_names) -> None:
    """Drop everything prepared from these tables (their upload was deleted)."""
    names = set(table_names)
    with _LOCK:
        for key in [k for k in _PREPARED if _sheet_tables(k) & names]:
            del _PREPARED[key]


def _prepare(frame: pd.DataFrame, kinds: dict[str, str], labels: dict[str, str]) -> Prepared:
    frame = frame.copy()
    select, fields = [], []
    for col in frame.columns:
        kind = kinds.get(col) or ("number" if pd.api.types.is_numeric_dtype(frame[col]) else "text")
        q = quote_ident(col)
        scale = None
        if kind == "number":
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("float64")
            scale = decimal_scale(frame[col])
            expr = f"CAST({q} AS DECIMAL(18, {scale}))" if scale is not None else f"CAST({q} AS DOUBLE)"
        elif kind == "date":
            values = pd.to_datetime(frame[col], errors="coerce")
            frame[col] = values
            date_only = bool(((values.dt.normalize() == values) | values.isna()).all())
            expr = f"CAST({q} AS DATE)" if date_only else f"CAST({q} AS TIMESTAMP)"
        else:
            frame[col] = frame[col].astype("string")
            expr = f"CAST({q} AS VARCHAR)"
        select.append(f"{expr} AS {q}")
        fields.append(Field(col, labels.get(col, col), kind, scale))
    return frame, select, fields


def prepare_sheet(sheet: dict) -> Prepared:
    def build() -> Prepared:
        columns = sheet["profile"]["columns"]
        return _prepare(load_frame(sheet).drop(columns=ROWID), {c["name"]: c["kind"] for c in columns},
                        {c["name"]: c["label"] for c in columns})

    return cached(sheet_key(sheet), build)


_DATABASE: duckdb.DuckDBPyConnection | None = None


def _database() -> duckdb.DuckDBPyConnection:
    """The shared in-memory DuckDB, locked down once (opening one costs ~25 ms; a connection to it ~0.02 ms)."""
    global _DATABASE
    with _LOCK:
        if _DATABASE is None:
            # Use the machine's cores for big files (capped so one request cannot starve the others).
            database = duckdb.connect(":memory:", config={"threads": max(2, min(8, os.cpu_count() or 2)), "memory_limit": "1GB"})
            # No query can ever touch files, the network, extensions or settings.
            database.execute("SET enable_external_access = false")
            database.execute("SET lock_configuration = true")
            _DATABASE = database
            atexit.register(database.close)  # close cleanly when the backend stops
        return _DATABASE


class Session:
    """A private connection with one view per sheet (and optional extra tables).

    extra: name -> (frame, kinds, labels); a frame with ``attrs["cache_key"]`` is prepared once and remembered."""

    def __init__(self, sheets: list[dict], extra: dict[str, tuple[pd.DataFrame, dict[str, str], dict[str, str]]] | None = None):
        self.conn = _database().cursor()
        self.fields: dict[str, list[Field]] = {}
        self.titles: dict[str, str] = {}
        try:
            for n, sheet in enumerate(sheets):
                self._register(sheet["table_name"], prepare_sheet(sheet), n)
                self.titles[sheet["table_name"]] = sheet["sheet_name"]
            for n, (name, (frame, kinds, labels)) in enumerate((extra or {}).items(), start=len(sheets)):
                key = frame.attrs.get("cache_key")
                prepared = cached(("extra", name, key), lambda: _prepare(frame, kinds, labels)) if key else _prepare(frame, kinds, labels)
                self._register(name, prepared, n)
        except Exception:
            self.conn.close()
            raise

    def _register(self, table: str, prepared: Prepared, n: int) -> None:
        frame, select, fields = prepared
        source = f"_source_{n}"
        self.conn.register(source, frame)  # zero-copy, and visible to this connection only
        self.conn.execute(f"CREATE TEMP VIEW {quote_ident(table)} AS SELECT {', '.join(select) or '1 AS empty'} FROM {source}")
        self.fields[table] = fields

    # --- running queries ---

    def fetch(self, sql: str, params: list | None = None, limit: int | None = None) -> tuple[list[str], list[tuple]]:
        """Run trusted SQL (built by the app, values bound as parameters) with the time limit."""
        timer = threading.Timer(config.SQL_TIMEOUT_SECONDS, self.conn.interrupt)
        timer.start()
        try:
            cursor = self.conn.execute(sql, params or [])
            columns = [d[0] for d in cursor.description or []]
            rows = cursor.fetchall() if limit is None else cursor.fetchmany(limit)
        except duckdb.InterruptException as exc:
            raise QueryError(f"The query took longer than {config.SQL_TIMEOUT_SECONDS} seconds and was stopped.") from exc
        except duckdb.Error as exc:
            raise QueryError(_clean_error(exc)) from exc
        finally:
            timer.cancel()
        return columns, rows

    def query(self, sql: str, limit: int = config.SQL_RESULT_LIMIT) -> QueryResult:
        """Run one SELECT written by a person or the AI."""
        statement = sql.strip().rstrip(";").strip()
        if not statement:
            raise QueryError("The query is empty.")
        try:
            statements = self.conn.extract_statements(statement)
        except duckdb.Error as exc:
            raise QueryError(_clean_error(exc)) from exc
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise QueryError("Only one SELECT query at a time is allowed.")
        started = time.monotonic()
        columns, rows = self.fetch(statement, limit=limit + 1)
        return QueryResult(
            columns=columns,
            rows=[[json_value(v) for v in row] for row in rows[:limit]],
            truncated=len(rows) > limit,
            elapsed_ms=round((time.monotonic() - started) * 1000, 1),
        )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
