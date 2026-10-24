"""Analyse: group, total and filter a sheet without writing SQL (DuckDB underneath, pandas on top).

A request - table, measures (sum / count / average / min / max / distinct of a column), up to two
group-by columns (dates by day, month, FY quarter, FY or year), filters, sort and top N - becomes one
parameterised DuckDB query: values are bound as parameters, never pasted into the SQL. DuckDB groups
the exact DECIMAL columns; pandas then builds the table people see: averages from exact sums, the top N
with an "All others" row so the column still adds up, the optional pivot across a second column, and
the total. A second, ungrouped query computes the overall totals, and the groups must add up to them.
"""

from __future__ import annotations

import re
import time
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from .compat import to_timestamp
from .database import QueryError, quote_ident
from .duck import Field, Session, cached, json_value, sheet_key
from .excel_loader import to_number
from .formatting import indian

AGGS = ("sum", "count", "average", "min", "max", "distinct")
BUCKETS = ("none", "day", "month", "quarter", "fy", "year")
OPS = ("=", "!=", ">", ">=", "<", "<=", "between", "contains", "in", "blank", "not_blank")
SORTS = ("value_desc", "value_asc", "label")
MAX_MEASURES, MAX_GROUPS, MAX_FILTERS, MAX_LIMIT, MAX_ACROSS = 4, 2, 8, 500, 24
MAX_GROUP_ROWS = 5000

_MONEY = re.compile(r"amount|amt|val|value|total|taxable|tax|gst|cess|price|debit|credit|balance|lbr|labour|making|paid|due",
                    re.IGNORECASE)
_AGG_LABEL = {"sum": "Total {}", "average": "Average {}", "min": "Lowest {}", "max": "Highest {}", "distinct": "Number of different {}"}
_BUCKET_LABEL = {"day": "day", "month": "month", "quarter": "quarter", "fy": "financial year", "year": "year"}


class AnalysisError(ValueError):
    """The request cannot be run as asked. The message is shown to the user (or the AI)."""


# --- the request -------------------------------------------------------------------------------------


def _field(fields: dict[str, Field], name: str, what: str) -> Field:
    if name in fields:
        return fields[name]
    by_label = {f.label.strip().lower(): f for f in fields.values()}
    if name.strip().lower() in by_label:
        return by_label[name.strip().lower()]
    raise AnalysisError(f'{what}: no column "{name}". Columns: {", ".join(f.name for f in fields.values())}.')


def normalise(session: Session, spec: dict) -> dict:
    """Check the request against the table's columns and fill in defaults."""
    table = (spec.get("table") or "").strip()
    if not table and len(session.fields) == 1:
        table = next(iter(session.fields))
    if table not in session.fields:
        raise AnalysisError(f'No table "{table}". Tables: {", ".join(session.fields)}.')
    fields = {f.name: f for f in session.fields[table]}

    measures = []
    for m in spec.get("measures") or []:
        agg, column = m.get("agg"), (m.get("column") or "").strip()
        if agg not in AGGS:
            raise AnalysisError(f"Measure {agg!r} is not one of {', '.join(AGGS)}.")
        if agg == "count" and not column:
            measures.append({"agg": "count", "column": ""})
            continue
        if not column:
            raise AnalysisError(f"Choose a column for {agg}.")
        f = _field(fields, column, agg.title())
        if agg in ("sum", "average") and f.kind != "number":
            raise AnalysisError(f'"{f.label}" is not a number column, so it cannot be added up or averaged.')
        if agg in ("min", "max") and f.kind == "text":
            raise AnalysisError(f'"{f.label}" is text; lowest/highest work on numbers and dates.')
        measures.append({"agg": agg, "column": f.name})
    if not measures:
        raise AnalysisError("Choose at least one thing to show (for example the total of an amount column).")
    if len(measures) > MAX_MEASURES:
        raise AnalysisError(f"Show at most {MAX_MEASURES} measures at a time.")

    group_by = []
    for g in spec.get("group_by") or []:
        f = _field(fields, (g.get("column") or "").strip(), "Group by")
        bucket = g.get("bucket") or "none"
        if bucket not in BUCKETS:
            raise AnalysisError(f"Date grouping {bucket!r} is not one of {', '.join(BUCKETS)}.")
        if f.kind == "date" and bucket == "none":
            bucket = "month"
        elif f.kind != "date":
            bucket = "none"
        group_by.append({"column": f.name, "bucket": bucket})
    if len(group_by) > MAX_GROUPS:
        raise AnalysisError(f"Group by at most {MAX_GROUPS} columns.")

    filters = []
    for flt in spec.get("filters") or []:
        f = _field(fields, (flt.get("column") or "").strip(), "Filter")
        op = flt.get("op")
        if op not in OPS:
            raise AnalysisError(f"Filter {op!r} is not one of {', '.join(OPS)}.")
        entry = {"column": f.name, "op": op, "value": str(flt.get("value") or "").strip(),
                 "value2": str(flt.get("value2") or "").strip(), "values": [str(v).strip() for v in flt.get("values") or [] if str(v).strip()]}
        if f.kind == "date" and op not in ("blank", "not_blank"):
            # Dates are kept as the exact day used (YYYY-MM-DD), so the description and the spec show it.
            what = f'Filter on "{f.label}"'
            if op == "contains":
                raise AnalysisError(f"{what}: 'contains' works on text columns; for dates use between, >= or <=.")
            # Only the fields the operator uses: the tools always send value2 and values, often with filler.
            if op == "in":
                entry["values"] = [parse_date(v, what).isoformat() for v in entry["values"]]
            else:
                used = ("value", "value2") if op == "between" else ("value",)
                for k in used:
                    entry[k] = parse_date(entry[k], what).isoformat() if entry[k] else ""
        filters.append(entry)
    if len(filters) > MAX_FILTERS:
        raise AnalysisError(f"Use at most {MAX_FILTERS} filters.")

    sort = spec.get("sort") or ("label" if group_by and fields[group_by[0]["column"]].kind == "date" else "value_desc")
    if sort not in SORTS:
        raise AnalysisError(f"Sort {sort!r} is not one of {', '.join(SORTS)}.")
    limit = int(spec.get("limit") or 0)
    if not 0 <= limit <= MAX_LIMIT:
        raise AnalysisError(f"Top N must be between 1 and {MAX_LIMIT} (0 = all).")
    across = bool(spec.get("across")) and len(group_by) == 2
    return {"table": table, "measures": measures, "group_by": group_by, "filters": filters, "sort": sort,
            "limit": limit, "across": across}


# --- SQL ----------------------------------------------------------------------------------------------


def _group_sql(f: Field, bucket: str) -> str:
    q = quote_ident(f.name)
    if f.kind == "date":
        fy = f"(CASE WHEN month({q}) >= 4 THEN year({q}) ELSE year({q}) - 1 END)"
        fy_label = f"CAST({fy} AS VARCHAR) || '-' || lpad(CAST(({fy} + 1) % 100 AS VARCHAR), 2, '0')"
        expr = {
            "day": f"strftime({q}, '%Y-%m-%d')",
            "month": f"strftime({q}, '%Y-%m')",
            "year": f"strftime({q}, '%Y')",
            "fy": f"'FY ' || {fy_label}",
            "quarter": f"{fy_label} || ' Q' || CAST(((month({q}) + 8) % 12) // 3 + 1 AS VARCHAR)",
        }[bucket]
        return f"COALESCE({expr}, '(no date)')"
    if f.kind == "text":
        return f"COALESCE(NULLIF(trim({q}), ''), '(blank)')"
    return q  # numbers keep their value so they sort as numbers; blanks are labelled in pandas


def _measure_sql(f: Field | None, agg: str, i: int) -> list[str]:
    if f is None:
        return [f"COUNT(*) AS m{i}"]
    q = quote_ident(f.name)
    total = f"SUM({q})" if f.scale is not None else f"fsum({q})"  # exact DECIMAL; compensated sum for DOUBLE
    return {
        "sum": [f"{total} AS m{i}"],
        "average": [f"{total} AS m{i}", f"COUNT({q}) AS n{i}"],
        "count": [f"COUNT({q}) AS m{i}"],
        "distinct": [f"COUNT(DISTINCT {q}) AS m{i}"],
        "min": [f"MIN({q}) AS m{i}"],
        "max": [f"MAX({q}) AS m{i}"],
    }[agg]


# Only a time of day may follow the date. Any other text ("2025-04-01 to 2025-04-30", "01/04/2025 onwards")
# is refused, so a range typed into one field cannot quietly become its first day.
_TIME = r"(?:(?:T|\s+)\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*(?:[AaPp]\.?[Mm]\.?|Z|[+-]\d{2}:?\d{2})?)?"
_WEEKDAY = r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+)?"
_YEAR_FIRST = re.compile(r"(\d{4})[-/.\s](\d{1,2})[-/.\s](\d{1,2})" + _TIME)
_DAY_FIRST = re.compile(r"(\d{1,2})[-/.\s](\d{1,2})[-/.\s](\d{4}|\d{2})" + _TIME)
_COMPACT = re.compile(r"(\d{4})(\d{2})(\d{2})")
# "1 Apr 2025", "1-Apr-25" (the Tally / Excel default), "1st April, 2025"; month first only with a 4-digit year.
_DAY_MONTH = re.compile(_WEEKDAY + r"(\d{1,2})(?:st|nd|rd|th)?[-/.\s]*([a-z]+)\.?[-/.,'\s]*(\d{4}|\d{2})" + _TIME, re.IGNORECASE)
_MONTH_DAY = re.compile(_WEEKDAY + r"([a-z]+)\.?[-/.\s]*(\d{1,2})(?:st|nd|rd|th)?,?[-/.\s]*(\d{4})" + _TIME, re.IGNORECASE)
_MONTHS = {name: i for i, names in enumerate(
    [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
     ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
     ("dec", "december")], start=1) for name in names}


def _full_year(year: int) -> int:
    """A two-digit year, read as pandas / dateutil read it: within 50 years of today (99 -> 1999, 25 -> 2025)."""
    if year >= 100:
        return year
    this_year = date.today().year
    year += this_year // 100 * 100
    return year - 100 if year >= this_year + 50 else year


def parse_date(text: str, what: str) -> date:
    """A filter date: YYYY-MM-DD (also with / or .) is year-first; DD/MM/YYYY (also - or .) is day-first, as in India.
    Never guesses the other order: 04/13/2025 is refused rather than read as 13 April, so a range cannot shift."""
    text = text.strip()
    order = "YYYY-MM-DD"
    if m := _YEAR_FIRST.fullmatch(text) or _COMPACT.fullmatch(text):
        year, month, day = (int(g) for g in m.groups())
    elif m := _DAY_FIRST.fullmatch(text):
        order = "DD/MM/YYYY"
        day, month, year = (int(g) for g in m.groups())
    elif (m := _DAY_MONTH.fullmatch(text)) and m.group(2).lower() in _MONTHS:
        order = "a day, month and year"
        day, month, year = int(m.group(1)), _MONTHS[m.group(2).lower()], int(m.group(3))
    elif (m := _MONTH_DAY.fullmatch(text)) and m.group(1).lower() in _MONTHS:
        order = "a month, day and year"
        day, month, year = int(m.group(2)), _MONTHS[m.group(1).lower()], int(m.group(3))
    else:
        # Anything vaguer ("April 2025", "1/4", "2025-04") or with extra words is refused rather than guessed.
        raise AnalysisError(f'{what}: "{text}" is not one date (use YYYY-MM-DD or DD/MM/YYYY; for a range use "between").')
    try:
        return date(_full_year(year), month, day)
    except ValueError:
        raise AnalysisError(f'{what}: "{text}" is not a valid date as {order}.') from None


def _value(f: Field, text: str, what: str):
    if f.kind == "number":
        number = to_number(text)
        if number is None or (isinstance(number, float) and number != number):
            raise AnalysisError(f'{what}: "{text}" is not a number.')
        return Decimal(str(number))
    if f.kind == "date":
        return parse_date(text, what)
    return text


def _filter_sql(f: Field, flt: dict) -> tuple[str, list]:
    q, op, what = quote_ident(f.name), flt["op"], f'Filter on "{f.label}"'
    if op in ("blank", "not_blank"):
        blank = f"({q} IS NULL OR trim({q}) = '')" if f.kind == "text" else f"{q} IS NULL"
        return (blank if op == "blank" else f"NOT {blank}"), []
    if op == "in":
        if not flt["values"]:
            raise AnalysisError(f"{what}: give at least one value.")
        values = [_value(f, v, what) for v in flt["values"]]
        if f.kind == "text":
            return f"lower(trim({q})) IN ({', '.join('lower(trim(?))' for _ in values)})", values
        return f"{q} IN ({', '.join('?' for _ in values)})", values
    if not flt["value"]:
        raise AnalysisError(f"{what}: give a value.")
    value = _value(f, flt["value"], what)
    if f.kind == "text":
        if op == "contains":
            return f"contains(lower({q}), lower(?))", [value]
        if op == "=":
            return f"lower(trim({q})) = lower(trim(?))", [value]
        if op == "!=":
            return f"({q} IS NULL OR lower(trim({q})) <> lower(trim(?)))", [value]
        raise AnalysisError(f"{what}: text can be filtered with is, is not, contains, is one of, blank or not blank.")
    target = f"CAST({q} AS DATE)" if f.kind == "date" else q
    if op == "contains":
        raise AnalysisError(f"{what}: 'contains' works on text columns.")
    if op == "between":
        if not flt["value2"]:
            raise AnalysisError(f"{what}: give both ends of the range.")
        return f"{target} BETWEEN ? AND ?", [value, _value(f, flt["value2"], what)]
    if op == "!=":
        return f"({q} IS NULL OR {target} <> ?)", [value]
    return f"{target} {op} ?", [value]


# --- run ----------------------------------------------------------------------------------------------


def _decimals(f: Field | None, agg: str) -> int:
    if f is None or agg in ("count", "distinct"):
        return 0
    base = f.scale if f.scale is not None else 2
    if _MONEY.search(f.name) or _MONEY.search(f.label):
        base = max(base, 2)
    return min(base + 2, 6) if agg == "average" else base


def _average(total, count, decimals: int):
    if total is None or not count:
        return None
    if isinstance(total, Decimal):
        return (total / Decimal(count)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return round(total / count, decimals)


def describe(spec: dict, fields: dict[str, Field]) -> str:
    """The request in words, e.g. 'Total Fine and number of rows by Party Name, top 10'."""
    def name(col):
        return fields[col].label

    def show(m):
        if m["agg"] == "count":
            return "Number of rows" if not m["column"] else f"Number of {name(m['column'])}"
        label = name(m["column"])
        if m["agg"] == "sum" and label.lower().startswith("total"):
            return label  # "Total GST", not "Total Total GST"
        return _AGG_LABEL[m["agg"]].format(label)

    shows = [show(m) for m in spec["measures"]]
    text = " and ".join([", ".join(shows[:-1]), shows[-1]] if len(shows) > 1 else shows)
    if spec["group_by"]:
        parts = [f"{name(g['column'])} ({_BUCKET_LABEL[g['bucket']]})" if g["bucket"] != "none" else name(g["column"]) for g in spec["group_by"]]
        text += " by " + (f"{parts[0]}, across {parts[1]}" if spec["across"] else " and ".join(parts))
    words = {"=": "is", "!=": "is not", ">": "above", ">=": "at least", "<": "below", "<=": "at most", "contains": "contains",
             "in": "is one of", "blank": "is blank", "not_blank": "is not blank"}
    conditions = []
    for flt in spec["filters"]:
        col = name(flt["column"])
        if flt["op"] == "between":
            conditions.append(f"{col} from {flt['value']} to {flt['value2']}")
        elif flt["op"] in ("blank", "not_blank"):
            conditions.append(f"{col} {words[flt['op']]}")
        elif flt["op"] == "in":
            conditions.append(f"{col} is one of {', '.join(flt['values'])}")
        else:
            conditions.append(f"{col} {words[flt['op']]} {flt['value']}")
    if conditions:
        text += ", where " + " and ".join(conditions)
    if spec["limit"] and spec["group_by"] and not spec["across"]:
        text += f"; top {spec['limit']}"
    return text


def _sort_key(value):
    """Comparable form of a cell: numbers as numbers, text case-insensitively; blanks sort last (None)."""
    if value is None or value in ("(blank)", "(no date)"):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, date):
        return value.toordinal()
    return value


def _sorted_unique(values) -> list:
    unique = list(dict.fromkeys(values))
    return sorted(unique, key=lambda v: (_sort_key(v) is None, _sort_key(v) if _sort_key(v) is not None else 0))


def _add_up(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    total = values[0]
    for v in values[1:]:
        total += v
    return total


def _show(value, decimals: int) -> str:
    return indian(value, decimals) if isinstance(value, (int, float, Decimal)) else str(value)


def run(session: Session, request: dict) -> dict:
    started = time.monotonic()
    spec = normalise(session, request)
    fields = {f.name: f for f in session.fields[spec["table"]]}
    measures = [(m, fields.get(m["column"])) for m in spec["measures"]]
    groups = [(g, fields[g["column"]]) for g in spec["group_by"]]

    where, params = [], []
    for flt in spec["filters"]:
        sql, values = _filter_sql(fields[flt["column"]], flt)
        where.append(sql)
        params += values
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    aggregates = [s for i, (m, f) in enumerate(measures) for s in _measure_sql(f, m["agg"], i)]
    table = quote_ident(spec["table"])

    try:
        # The overall totals, computed by a separate query so the groups can be checked against them.
        cols, rows = session.fetch(f"SELECT {', '.join(aggregates)}, COUNT(*) AS _rows FROM {table}{where_sql}", params)
        overall = dict(zip(cols, rows[0]))
        if groups:
            keys = [f"{_group_sql(f, g['bucket'])} AS g{i}" for i, (g, f) in enumerate(groups)]
            cols, rows = session.fetch(f"SELECT {', '.join(keys)}, {', '.join(aggregates)} FROM {table}{where_sql} GROUP BY ALL",
                                       params, limit=MAX_GROUP_ROWS + 1)
            if len(rows) > MAX_GROUP_ROWS:
                raise AnalysisError(f"More than {MAX_GROUP_ROWS:,} groups; add a filter or group by fewer columns.")
            frame = pd.DataFrame(rows, columns=cols, dtype=object)
        else:
            frame = pd.DataFrame([overall], dtype=object)
    except QueryError as exc:
        raise AnalysisError(str(exc)) from exc

    decimals = [_decimals(f, m["agg"]) for m, f in measures]
    for i, (m, _f) in enumerate(measures):
        if m["agg"] == "average":  # exact sum / count, rounded half-up like Excel
            frame[f"s{i}"] = frame[f"m{i}"]
            frame[f"m{i}"] = [_average(s, n, decimals[i]) for s, n in zip(frame[f"s{i}"], frame[f"n{i}"])]
            overall[f"m{i}"] = _average(overall[f"m{i}"], overall[f"n{i}"], decimals[i])
    for i, (_g, f) in enumerate(groups):
        if f.kind == "number":
            frame[f"g{i}"] = frame[f"g{i}"].map(lambda v: "(blank)" if v is None else v)

    def measure_label(m):
        return describe({**spec, "measures": [m], "group_by": [], "filters": [], "limit": 0}, fields)

    checks = []
    if groups:
        # Proof: each additive measure's groups add up to the overall figure from the second query.
        for i, (m, _f) in enumerate(measures):
            if m["agg"] in ("sum", "count"):
                total, expected = _add_up(frame[f"m{i}"]) or 0, overall[f"m{i}"] or 0
                same = total == expected if not isinstance(total, float) else abs(total - float(expected)) < 1e-6
                checks.append({"level": "ok" if same else "warning",
                               "message": f"The groups add up to the overall {measure_label(m)}: {_show(expected, decimals[i])}." if same
                               else f"The groups add up to {_show(total, decimals[i])} but the overall {measure_label(m)} is {_show(expected, decimals[i])}."})
        if groups[0][1].kind == "text":
            names = list(dict.fromkeys(str(v) for v in frame["g0"]))  # each name once (a pivot repeats them)
            folded = [re.sub(r"\s+", " ", n.strip().lower()) for n in names]
            clashes = sorted({n for n, k in zip(names, folded) if folded.count(k) > 1})
            if clashes:
                checks.append({"level": "warning", "message": "Some names differ only in capitals or spaces and are counted separately: "
                               + ", ".join(clashes[:8]) + ("…" if len(clashes) > 8 else "") + "."})

        # DuckDB returns groups in no fixed order (it varies run to run and between versions), so put them in label
        # order first: groups with equal values then always come out the same way.
        frame = frame.sort_values([f"g{i}" for i in range(len(groups))], na_position="last", kind="stable",
                                  key=lambda s: s.map(_sort_key))
        by = "g0" if spec["sort"] == "label" else "m0"
        frame = frame.sort_values(by, ascending=spec["sort"] != "value_desc", na_position="last", kind="stable",
                                  key=lambda s: s.map(_sort_key)).reset_index(drop=True)
    group_count = len(frame) if groups else 0

    # Top N: the rest is folded into one "All others" row so the column still adds up to the total.
    others = None
    if groups and spec["limit"] and not spec["across"] and len(frame) > spec["limit"]:
        rest = frame.iloc[spec["limit"]:]
        frame = frame.iloc[: spec["limit"]]
        others = {"g0": f"All others ({len(rest)})", "_kind": "others"}
        for i, (m, _f) in enumerate(measures):
            values = [v for v in rest[f"m{i}"] if v is not None]
            others[f"m{i}"] = {
                "sum": _add_up(values), "count": _add_up(values), "min": min(values) if values else None,
                "max": max(values) if values else None, "distinct": None,  # distinct counts do not add up across groups
                "average": _average(_add_up(rest.get(f"s{i}", [])), _add_up(rest.get(f"n{i}", [])) or 0, decimals[i]) if m["agg"] == "average" else None,
            }[m["agg"]]

    def cell(value):
        return value if isinstance(value, str) else json_value(value)

    columns, out_rows, total_row = [], [], None
    if spec["across"]:
        # Pivot: first group down the side, second across the top, the first measure in the cells.
        (_g0, f0), (_g1, f1) = groups
        m0 = measures[0][0]
        across_values = _sorted_unique(frame["g1"])
        if len(across_values) > MAX_ACROSS:
            raise AnalysisError(f'"{f1.label}" has {len(across_values)} values; spreading it across allows at most {MAX_ACROSS}. '
                                "Filter it, or group dates by month or FY instead of day.")
        cells = {(r["g0"], r["g1"]): r["m0"] for r in frame.to_dict("records")}
        additive = m0["agg"] in ("sum", "count")
        columns.append({"key": "g0", "label": f0.label, "format": "text"})
        columns += [{"key": f"c{j}", "label": str(cell(v)), "format": "number", "decimals": decimals[0]} for j, v in enumerate(across_values)]
        if additive:
            columns.append({"key": "row_total", "label": "Total", "format": "number", "decimals": decimals[0]})
        # Rows in label order, or by their row total (largest or smallest first).
        side = list(dict.fromkeys(frame["g0"]))
        if spec["sort"] == "label":
            side = _sorted_unique(side)
        else:
            totals = {k: _add_up(cells.get((k, v)) for v in across_values) for k in side}
            side.sort(key=lambda k: (totals[k] is None, -float(totals[k] or 0) if spec["sort"] == "value_desc" else float(totals[k] or 0)))
        for key in side:
            row = {"g0": cell(key)}
            for j, v in enumerate(across_values):
                row[f"c{j}"] = json_value(cells.get((key, v)))
            if additive:
                row["row_total"] = json_value(_add_up(cells.get((key, v)) for v in across_values))
            out_rows.append(row)
        if additive:
            total_row = {"g0": "Total", "row_total": json_value(overall["m0"])}
            for j, v in enumerate(across_values):
                total_row[f"c{j}"] = json_value(_add_up(value for (_k, a), value in cells.items() if a == v))
        description = describe({**spec, "measures": [m0]}, fields)
    else:
        for i, (g, f) in enumerate(groups):
            label = f.label if g["bucket"] == "none" else f"{f.label} ({_BUCKET_LABEL[g['bucket']]})"
            columns.append({"key": f"g{i}", "label": label, "format": "text"})
        for i, ((m, f), d) in enumerate(zip(measures, decimals)):
            fmt = "date" if f is not None and f.kind == "date" and m["agg"] in ("min", "max") else "number"
            columns.append({"key": f"m{i}", "label": measure_label(m), "format": fmt, "decimals": d})
        keys = [c["key"] for c in columns]
        out_rows = [{k: cell(record.get(k)) for k in keys} for record in frame.to_dict("records")]
        if others:
            out_rows.append({**{k: cell(others.get(k)) for k in keys}, "_kind": "others"})
        if groups:
            total_row = {"g0": "Total", **{f"m{i}": json_value(overall[f"m{i}"]) for i in range(len(measures))}}
            for i, (m, _f) in enumerate(measures):
                if m["agg"] == "distinct":
                    total_row[f"m{i}"] = json_value(overall[f"m{i}"])  # different values overall (not the sum of the groups)
        description = describe(spec, fields)

    return {
        "spec": spec,
        "table_title": session.titles.get(spec["table"], spec["table"]),
        "description": description,
        "columns": columns,
        "rows": out_rows,
        "total": total_row,
        "groups": group_count,
        "rows_matched": int(overall["_rows"]),
        "checks": checks,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
    }


# --- Sales + purchase sets: both registers as one table ----------------------------------------------

REGISTER_COLUMNS = {  # normalised column -> (label, kind)
    "register": ("Register", "text"), "date": ("Date", "date"), "party": ("Party", "text"), "invoice_no": ("Invoice no.", "text"),
    "gstin": ("GSTIN", "text"), "item": ("Item", "text"), "taxable": ("Taxable value", "number"), "cgst": ("CGST", "number"),
    "sgst": ("SGST", "number"), "igst": ("IGST", "number"), "cess": ("Cess", "number"), "gst": ("Total GST", "number"),
    "invoice_value": ("Invoice value", "number"),
}


def register_table(sheets: list[dict]) -> tuple[pd.DataFrame, dict[str, str], dict[str, str]] | None:
    """Both registers stacked in standard columns (amounts in rupees), or None if a sheet lacks amounts.
    Built once per version of the sheets and remembered (see duck.cached)."""
    key = ("registers", tuple(sheet_key(s) + (s.get("register"),) for s in sheets))
    return cached(key, lambda: _register_table(sheets, key))


def _register_table(sheets: list[dict], key: tuple) -> tuple[pd.DataFrame, dict[str, str], dict[str, str]] | None:
    from .books import REGISTERS, BookError, _normalise

    frames = []
    for sheet in sheets:
        if sheet.get("register") not in REGISTERS:
            continue
        try:
            frame, _notes, _others = _normalise(sheet)
        except BookError:
            return None
        out = pd.DataFrame({"register": "Sales" if sheet["register"] == "sales" else "Purchases", "date": frame["date"],
                            "party": frame["party"], "invoice_no": frame["invoice_no"], "gstin": frame["gstin"], "item": frame["item"]})
        for col in ("taxable", "cgst", "sgst", "igst", "cess", "invoice_value"):
            out[col] = frame[col].astype("int64") / 100  # whole paise -> rupees; DuckDB stores them as exact DECIMAL(18, 2)
        out["gst"] = (frame["tax"] + frame["cess"]).astype("int64") / 100
        frames.append(out)
    if not frames:
        return None
    combined = pd.concat(frames, ignore_index=True)[list(REGISTER_COLUMNS)]
    combined.attrs["cache_key"] = key  # lets the DuckDB session reuse its prepared copy
    return combined, {k: v[1] for k, v in REGISTER_COLUMNS.items()}, {k: v[0] for k, v in REGISTER_COLUMNS.items()}
