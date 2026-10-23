"""Column statistics and accounting summaries, computed with pandas and NumPy.

``profile_sheet`` runs once per sheet at upload time; the result is stored as JSON next to
the sheet's table and sent to the frontend as-is.
"""

import math
import re

import numpy as np
import pandas as pd

# Column-name patterns (matched against the cleaned snake_case names).
_IDENTIFIER = re.compile(
    r"(^|_)(id|no|num|number|code|ref|reference|sr|sl|serial|pin|pincode|phone|mobile|gstin|pan|year)(_|$)"
)
_DEBIT = re.compile(r"(^|_)(debit|debits|dr|withdrawal|withdrawals|outflow|paid_out)(_|$)")
_CREDIT = re.compile(r"(^|_)(credit|credits|cr|deposit|deposits|inflow|paid_in)(_|$)")
_BALANCE = re.compile(r"(^|_)(balance|bal|closing|opening)(_|$)")
_TAX = re.compile(r"(^|_)(gst|cgst|sgst|igst|utgst|cess|tax|tds|tcs|vat)(_|$)")
_AMOUNT_PRIORITY = [
    re.compile(p)
    for p in (
        r"(^|_)(amount|amt)(_|$)",
        r"(^|_)(net|total|grand_total)(_|$)",
        r"(^|_)(value|sales|revenue|expense|expenses|cost|price)(_|$)",
    )
]
_CATEGORY_PRIORITY = [
    re.compile(p)
    for p in (
        r"(^|_)(category|ledger|head|account|group|type|class)(_|$)",
        r"(^|_)(party|vendor|customer|supplier|client|payee|name)(_|$)",
        r"(^|_)(particulars|description|narration|details|item|product)(_|$)",
    )
]
_DATE_NAME = re.compile(r"date|dt|period|month")

MAX_MONTHS = 36
TOP_CATEGORIES = 10


def column_kind(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "text"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    return "text"


def _floats(series: pd.Series) -> np.ndarray:
    """Non-missing values as a float64 NumPy array."""
    arr = series.to_numpy(dtype="float64", na_value=np.nan)
    return arr[~np.isnan(arr)]


def _sum(values: np.ndarray) -> float:
    """Exactly rounded float sum (no build-up of rounding error over many rows)."""
    return math.fsum(values)


def _num(value) -> float:
    return round(float(value), 4)


def _column_profile(series: pd.Series, name: str, label: str) -> dict:
    kind = column_kind(series)
    non_null = int(series.notna().sum())
    profile = {
        "name": name,
        "label": label,
        "kind": kind,
        "non_null": non_null,
        "nulls": int(len(series) - non_null),
        "unique": int(series.nunique(dropna=True)),
        "role": None,
        "stats": None,
    }

    if kind == "number":
        if _IDENTIFIER.search(name):
            profile["role"] = "identifier"
            return profile
        values = _floats(series)
        if values.size:
            p25, median, p75 = np.percentile(values, [25, 50, 75])
            profile["stats"] = {
                "sum": _num(_sum(values)),
                "mean": _num(np.mean(values)),
                "median": _num(median),
                "std": _num(np.std(values, ddof=1)) if values.size > 1 else 0.0,
                "min": _num(np.min(values)),
                "max": _num(np.max(values)),
                "p25": _num(p25),
                "p75": _num(p75),
                "negatives": int(np.count_nonzero(values < 0)),
                "zeros": int(np.count_nonzero(values == 0)),
            }
    elif kind == "date":
        present = series.dropna()
        if not present.empty:
            first, last = present.min(), present.max()
            profile["stats"] = {
                "min": first.strftime("%Y-%m-%d"),
                "max": last.strftime("%Y-%m-%d"),
                "span_days": int((last - first).days),
            }
    else:
        top = series.value_counts(dropna=True).head(5)
        profile["stats"] = {"top": [{"value": str(v), "count": int(c)} for v, c in top.items()]}
    return profile


def _total_label(label: str) -> str:
    return label if "total" in label.lower() else f"Total {label}"


def _first_match(columns: list[str], patterns: list[re.Pattern], exclude: set[str] = frozenset()) -> str | None:
    for pattern in patterns:
        for col in columns:
            if col not in exclude and pattern.search(col):
                return col
    return None


def _pick_category(df: pd.DataFrame, text_cols: list[str]) -> str | None:
    """A text column that groups rows into a manageable number of buckets."""
    limit = max(2, min(100, int(len(df) * 0.6)))
    usable = [c for c in text_cols if 2 <= df[c].nunique(dropna=True) <= limit]
    return _first_match(usable, _CATEGORY_PRIORITY)


def accounting_summary(df: pd.DataFrame, kinds: dict[str, str], labels: dict[str, str]) -> dict:
    numeric = [c for c in df.columns if kinds[c] == "number" and not _IDENTIFIER.search(c)]
    dates = [c for c in df.columns if kinds[c] == "date"]
    texts = [c for c in df.columns if kinds[c] == "text"]

    tax_cols = [c for c in numeric if _TAX.search(c)]
    balance_cols = {c for c in numeric if _BALANCE.search(c)}
    debit = _first_match(numeric, [_DEBIT], exclude=set(tax_cols))
    credit = _first_match(numeric, [_CREDIT], exclude=set(tax_cols))
    if not (debit and credit):
        debit = credit = None
    amount = _first_match(
        numeric,
        _AMOUNT_PRIORITY,
        exclude=set(tax_cols) | balance_cols | {debit, credit},
    )
    if amount is None and not debit and len(numeric) == 1 and numeric[0] not in balance_cols:
        amount = numeric[0]
    date_col = next((c for c in dates if _DATE_NAME.search(c)), dates[0] if dates else None)
    category = _pick_category(df, texts)

    label = lambda col: labels.get(col, col)  # noqa: E731
    totals: list[dict] = []

    if debit and credit:
        dr, cr = _floats(df[debit]), _floats(df[credit])
        difference = _sum(dr) - _sum(cr)
        totals += [
            {"label": _total_label(label(debit)), "value": _num(_sum(dr)), "format": "money"},
            {"label": _total_label(label(credit)), "value": _num(_sum(cr)), "format": "money"},
            {
                "label": f"{label(debit)} − {label(credit)}",
                "value": _num(difference),
                "format": "money",
                "hint": "Balanced" if abs(difference) < 0.005 else None,
            },
        ]

    if amount:
        values = _floats(df[amount])
        if values.size and np.any(values < 0) and np.any(values > 0):
            totals += [
                {"label": "Inflows", "value": _num(_sum(values[values > 0])), "format": "money"},
                {"label": "Outflows", "value": _num(_sum(values[values < 0])), "format": "money"},
                {"label": f"Net {label(amount)}", "value": _num(_sum(values)), "format": "money"},
            ]
        elif values.size:
            totals += [
                {"label": _total_label(label(amount)), "value": _num(_sum(values)), "format": "money"},
                {"label": f"Average {label(amount)}", "value": _num(np.mean(values)), "format": "money"},
                {"label": f"Largest {label(amount)}", "value": _num(np.max(values)), "format": "money"},
            ]

    for col in tax_cols[:4]:
        totals.append({"label": _total_label(label(col)), "value": _num(_sum(_floats(df[col]))), "format": "money"})

    measures = [debit, credit] if debit and credit else ([amount] if amount else [])

    period = None
    monthly = None
    if date_col:
        present = df[date_col].dropna()
        if not present.empty:
            period = {"from": present.min().strftime("%Y-%m-%d"), "to": present.max().strftime("%Y-%m-%d")}
        if measures and not present.empty:
            monthly = _monthly_table(df, date_col, measures, label)

    by_category = _category_table(df, category, measures, label) if category and measures else None

    return {
        "detected": {
            "date": date_col,
            "amount": amount,
            "debit": debit,
            "credit": credit,
            "category": category,
            "tax": tax_cols,
        },
        "period": period,
        "totals": totals,
        "monthly": monthly,
        "by_category": by_category,
    }


def _monthly_table(df: pd.DataFrame, date_col: str, measures: list[str], label) -> dict:
    month = df[date_col].dt.to_period("M").rename("month")
    values = df[measures].astype("float64")
    grouped = values.groupby(month).agg(["sum", "count"]).sort_index().tail(MAX_MONTHS)

    columns = [{"key": "month", "label": "Month", "format": "text"}]
    columns += [{"key": m, "label": label(m), "format": "money"} for m in measures]
    if len(measures) == 2:
        columns.append({"key": "net", "label": f"{label(measures[0])} − {label(measures[1])}", "format": "money"})
    columns.append({"key": "entries", "label": "Entries", "format": "count"})

    sums = grouped.xs("sum", axis=1, level=1).to_numpy()
    counts = grouped.xs("count", axis=1, level=1).to_numpy().max(axis=1)
    rows = []
    for i, period in enumerate(grouped.index):
        row = {"month": period.strftime("%b %Y")}
        for j, m in enumerate(measures):
            row[m] = _num(sums[i, j])
        if len(measures) == 2:
            row["net"] = _num(sums[i, 0] - sums[i, 1])
        row["entries"] = int(counts[i])
        rows.append(row)
    return {"columns": columns, "rows": rows}


def _category_table(df: pd.DataFrame, category: str, measures: list[str], label) -> dict:
    values = df[measures].astype("float64")
    grouped = values.groupby(df[category].fillna("(blank)")).agg(["sum", "count"])
    sums = grouped.xs("sum", axis=1, level=1)
    counts = grouped.xs("count", axis=1, level=1).max(axis=1)

    weight = np.abs(sums.to_numpy()).sum(axis=1)
    total_weight = weight.sum()
    order = np.argsort(-weight)[:TOP_CATEGORIES]

    columns = [{"key": "name", "label": label(category), "format": "text"}]
    columns += [{"key": m, "label": label(m), "format": "money"} for m in measures]
    columns += [
        {"key": "entries", "label": "Entries", "format": "count"},
        {"key": "share", "label": "Share", "format": "percent"},
    ]
    rows = []
    for i in order:
        row = {"name": str(sums.index[i])}
        for m in measures:
            row[m] = _num(sums.iloc[i][m])
        row["entries"] = int(counts.iloc[i])
        row["share"] = _num(weight[i] / total_weight) if total_weight else 0.0
        rows.append(row)
    return {
        "category_column": category,
        "groups": int(len(sums)),
        "columns": columns,
        "rows": rows,
    }


def profile_sheet(
    df: pd.DataFrame, labels: dict[str, str], checks: list[dict], calculated: set[str] = frozenset()
) -> dict:
    """``calculated`` columns (added in the app) get statistics but are never picked as debit/credit/tax/etc."""
    kinds = {col: column_kind(df[col]) for col in df.columns}
    source = df.drop(columns=[c for c in calculated if c in df.columns])
    return {
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "columns": [_column_profile(df[col], col, labels.get(col, col)) for col in df.columns],
        "summary": accounting_summary(source, kinds, labels),
        "checks": checks,
    }
