"""Change a sheet after it was imported: add or delete entries, add calculated columns, keep notes.

After every change the sheet's statistics and summaries are recomputed with pandas/NumPy
from the stored table, so every total on screen reflects the current data.
"""

import json
import math

import numpy as np
import pandas as pd
from sqlalchemy import text, update

from .analytics import profile_sheet
from .calc import columns_in, evaluate_columns
from .database import dataset_sheets, engine, quote_ident
from .excel_loader import clean_name, parse_date_input, to_number

ROWID = "_rowid"
_PREVIEW_ROWS = 20


class EditError(ValueError):
    """The change was rejected. The message is shown to the user."""


def load_frame(sheet: dict) -> pd.DataFrame:
    """The sheet's current table with column types restored (dates as datetimes) and its rowids."""
    table = quote_ident(sheet["table_name"])
    with engine.connect() as conn:
        frame = pd.read_sql_query(f"SELECT rowid AS {ROWID}, * FROM {table} ORDER BY rowid", conn)
    kinds = {c["name"]: c["kind"] for c in sheet["profile"]["columns"]}
    for col in frame.columns.drop(ROWID):
        kind = kinds.get(col, "number" if pd.api.types.is_numeric_dtype(frame[col]) else "text")
        if kind == "date":
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
        elif kind == "number":
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        else:
            frame[col] = frame[col].astype("string")
    return frame


def refresh_profile(sheet: dict, change: dict, extra_labels: dict[str, str] | None = None) -> dict:
    """Recompute and store the sheet's profile after a change; returns the new profile."""
    old = sheet["profile"]
    frame = load_frame(sheet).drop(columns=ROWID)
    labels = {c["name"]: c["label"] for c in old["columns"]} | (extra_labels or {})
    edits = {"added": 0, "deleted": 0, "columns": 0} | old.get("edits", {})
    for key, count in change.items():
        edits[key] += count

    summary = ", ".join(
        f"{count} {one if count == 1 else many}"
        for count, one, many in (
            (edits["added"], "entry added", "entries added"),
            (edits["deleted"], "entry deleted", "entries deleted"),
            (edits["columns"], "calculated column added", "calculated columns added"),
        )
        if count
    )
    checks = [c for c in old.get("checks", []) if not c.get("edit")]
    checks.append({
        "level": "info",
        "edit": True,
        "message": f"Changed in the app after upload: {summary}. The checks above describe the original file.",
    })

    calculated = list(old.get("calculated_columns", [])) + [c for c in (extra_labels or {}) if c not in old.get("calculated_columns", [])]
    profile = profile_sheet(frame, labels, checks, calculated=set(calculated))
    profile["edits"] = edits
    profile["calculated_columns"] = calculated
    for key in ("user_notes", "mapping", "classification"):
        if old.get(key) is not None:
            profile[key] = old[key]
    _store(sheet["table_name"], profile, len(frame))
    return profile


def _store(table_name: str, profile: dict, row_count: int | None = None) -> None:
    values = {"profile_json": json.dumps(profile)}
    if row_count is not None:
        values["row_count"] = row_count
    with engine.begin() as conn:
        conn.execute(update(dataset_sheets).where(dataset_sheets.c.table_name == table_name).values(**values))


def save_notes(sheet: dict, notes: str) -> dict:
    profile = sheet["profile"] | {"user_notes": notes.strip() or None}
    _store(sheet["table_name"], profile)
    return profile


def save_setup(sheet: dict, mapping: dict[str, str] | None, classification: dict[str, str] | None) -> dict:
    """Store the user's column roles and account groups (None leaves that part unchanged)."""
    names = {c["name"] for c in sheet["profile"]["columns"]}
    profile = dict(sheet["profile"])
    if mapping is not None:
        unknown = [v for v in mapping.values() if v and v not in names]
        if unknown:
            raise EditError(f"Unknown column: {unknown[0]}.")
        profile["mapping"] = {k: v for k, v in mapping.items() if v}
    if classification is not None:
        profile["classification"] = {k: v for k, v in classification.items() if v}
    _store(sheet["table_name"], profile)
    return profile


def list_rows(sheet: dict, offset: int, limit: int, search: str | None) -> dict:
    table = quote_ident(sheet["table_name"])
    columns = [c["name"] for c in sheet["profile"]["columns"]]
    where, params = "", {}
    if search:
        where = " WHERE " + " OR ".join(f"CAST({quote_ident(c)} AS TEXT) LIKE :q" for c in columns)
        params["q"] = f"%{search.strip()}%"
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {table}{where}"), params).scalar_one()
        result = conn.execute(
            text(f"SELECT rowid AS {ROWID}, * FROM {table}{where} ORDER BY rowid LIMIT :limit OFFSET :offset"),
            params | {"limit": limit, "offset": offset},
        )
        names = list(result.keys())
        rows = [[_cell(v) for v in row] for row in result]
    return {"columns": names, "rows": rows, "total": total, "offset": offset}


def _cell(value):
    if isinstance(value, float):
        return round(value, 8) if math.isfinite(value) else None
    return value


def add_row(sheet: dict, values: dict[str, str | float | None]) -> None:
    record = {}
    for col in sheet["profile"]["columns"]:
        raw = values.get(col["name"])
        if raw is None or str(raw).strip() == "":
            record[col["name"]] = None
            continue
        if col["kind"] == "number":
            number = to_number(raw)
            if math.isnan(number):
                raise EditError(f'"{col["label"]}" must be a number (got "{raw}").')
            record[col["name"]] = number
        elif col["kind"] == "date":
            try:
                stamp = parse_date_input(str(raw))
            except ValueError as exc:
                raise EditError(f'"{col["label"]}" must be a date: {exc}') from None
            record[col["name"]] = stamp.strftime("%Y-%m-%d") if stamp == stamp.normalize() else stamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            record[col["name"]] = str(raw).strip()
    if all(v is None for v in record.values()):
        raise EditError("Enter at least one value.")

    names = list(record)
    placeholders = ", ".join(f":p{i}" for i in range(len(names)))
    with engine.begin() as conn:
        conn.execute(
            text(f"INSERT INTO {quote_ident(sheet['table_name'])} ({', '.join(map(quote_ident, names))}) VALUES ({placeholders})"),
            {f"p{i}": record[name] for i, name in enumerate(names)},
        )


def delete_row(sheet: dict, rowid: int) -> None:
    with engine.begin() as conn:
        deleted = conn.execute(
            text(f"DELETE FROM {quote_ident(sheet['table_name'])} WHERE rowid = :r"), {"r": rowid}
        ).rowcount
    if not deleted:
        raise EditError("That entry no longer exists.")


def calculate(sheet: dict, expression: str) -> tuple[pd.DataFrame, pd.Series, dict]:
    """Evaluate a column formula. Returns the frame, the per-row result and summary statistics."""
    frame = load_frame(sheet)
    result = evaluate_columns(expression, frame)
    values = result.to_numpy(dtype="float64", na_value=np.nan)
    present = values[~np.isnan(values)]
    stats = {
        "count": int(present.size),
        "sum": round(math.fsum(present), 6) if present.size else 0.0,
        "mean": round(float(np.mean(present)), 6) if present.size else None,
        "min": float(np.min(present)) if present.size else None,
        "max": float(np.max(present)) if present.size else None,
    }
    return frame, result, stats


def check_formula(sheet: dict, target: str, expression: str, tolerance: float, frame: pd.DataFrame | None = None) -> dict:
    """Test "target = expression" on every row: how many rows match within the tolerance, and examples that don't."""
    frame = load_frame(sheet) if frame is None else frame
    if target not in frame.columns or target == ROWID:
        raise EditError(f'Unknown column "{target}".')
    if not pd.api.types.is_numeric_dtype(frame[target]):
        raise EditError(f'Column "{target}" is not a number column.')
    expected = evaluate_columns(expression, frame)
    actual = frame[target].astype("float64")
    present = actual.notna().to_numpy()
    diff = (actual - expected).abs().to_numpy()
    tolerance = abs(float(tolerance))
    matches = present & (diff <= tolerance + 1e-9)
    mismatched = present & ~matches
    examples = [
        {"row": int(r), "actual": _cell(a), "expected": _cell(round(e, 6)), "difference": _cell(round(a - e, 6))}
        for r, a, e in zip(frame.loc[mismatched, ROWID].head(8), actual[mismatched].head(8), expected[mismatched].head(8))
    ]
    return {
        "target": target,
        "expression": expression,
        "tolerance": tolerance,
        "rows_checked": int(present.sum()),
        "rows_blank": int((~present).sum()),
        "matches": int(matches.sum()),
        "mismatches": int(mismatched.sum()),
        "max_difference": _cell(round(float(np.nanmax(diff[present])), 6)) if present.any() else None,
        "examples": examples,
    }


def preview(sheet: dict, expression: str, frame: pd.DataFrame, result: pd.Series) -> dict:
    used = columns_in(expression)
    labels = {c["name"]: c["label"] for c in sheet["profile"]["columns"]}
    head = frame[used].head(_PREVIEW_ROWS).astype(object).where(frame[used].head(_PREVIEW_ROWS).notna(), None)
    rows = [[_cell(v) for v in row] + [_cell(r)] for row, r in zip(head.itertuples(index=False), result.head(_PREVIEW_ROWS))]
    return {"columns": [labels.get(c, c) for c in used] + ["Result"], "rows": rows}


def save_column(sheet: dict, label: str, result: pd.Series, frame: pd.DataFrame) -> str:
    """Store a calculated result as a new number column; returns the new column's name."""
    label = label.strip()
    if not label:
        raise EditError("Give the new column a name.")
    existing = {c["name"] for c in sheet["profile"]["columns"]}
    base = clean_name(label)
    name, n = base, 2
    while name in existing or name == ROWID:
        name, n = f"{base}_{n}", n + 1
    table = quote_ident(sheet["table_name"])
    with engine.begin() as conn:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {quote_ident(name)} REAL")
        conn.execute(
            text(f"UPDATE {table} SET {quote_ident(name)} = :v WHERE rowid = :r"),
            [{"v": None if pd.isna(v) else float(v), "r": int(r)} for v, r in zip(result, frame[ROWID])],
        )
    return name
