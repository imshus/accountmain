"""Pieces every chat model shares: the instructions, the table context and the tools (analyse, SQL, calculate)."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field

import pandas as pd

from .. import analysis
from ..calc import CalcError, evaluate_number, format_decimal
from ..database import QueryError, engine, quote_ident, read_preview, run_select
from ..duck import Session, prepare_sheet, sheet_key
from ..editing import ROWID, EditError, load_frame

ROWS_SHOWN_TO_MODEL = 100
SAMPLE_ROWS = 3
MAX_TOOL_ROUNDS = 12

SQL_TOOL_DESCRIPTION = (
    "Run one read-only DuckDB SELECT statement against the uploaded tables and return the result as JSON. "
    "Use it only for what analyse cannot do (joins, row-level lookups, calculations across columns of one row)."
)
SQL_QUERY_DESCRIPTION = "A single SELECT (or WITH ... SELECT) statement in DuckDB SQL."
ANALYSE_TOOL_DESCRIPTION = (
    "Totals, counts, averages, lowest/highest values and breakdowns of one table, without SQL: choose measures, up to two "
    "group-by columns (dates by month, quarter, fy or year), filters, sort and top N. Runs on exact decimals, returns the "
    "overall total, folds groups beyond the top N into an 'All others' row, and proves the groups add up to the total. "
    "Prefer it for every total, count, average or breakdown question."
)
ANALYSE_PARAMS = {
    "table": "Table name, e.g. ds2_sheet1.",
    "measures": "1-4 things to compute. agg: sum | count | average | min | max | distinct. column: a column name; "
                "for count, an empty string counts rows.",
    "group_by": "0-2 columns to break the figures down by. bucket groups a date column by day | month | quarter | fy | year "
                "(Indian financial year from April); use none for other columns.",
    "filters": "Conditions every counted row must meet. op: = | != | > | >= | < | <= | between (value and value2) | "
               "contains | in (values) | blank | not_blank. Text matches ignore capitals; dates as YYYY-MM-DD. "
               "Unused value fields are empty strings or an empty list.",
    "sort": "value_desc (largest first), value_asc, or label (alphabetical / date order).",
    "limit": "Show only the top N groups (0 = all); the rest become one 'All others' row.",
    "across": "true to spread the second group-by column across as columns (a pivot table) using the first measure.",
}
CALC_TOOL_DESCRIPTION = (
    "Exact decimal arithmetic. Use it for every number you derive yourself (differences, totals of figures from "
    "different queries, percentages, averages) instead of calculating in your head."
)
CALC_EXPRESSION_DESCRIPTION = (
    "Arithmetic on plain numbers without thousands separators, e.g. (1192634 / 2593364) * 100 or "
    "round(458000.5 - 12000.25, 2). Allowed: + - * / brackets % round abs min max."
)

SYSTEM_PROMPT = """You are the data analyst inside Accounts.ai, an accounting app. The user uploaded a spreadsheet and each sheet is a table you can analyse, described in <tables> below. You are in a chat with the user: earlier messages give context for follow-up questions such as "and in June?" or "split that by customer".

Accuracy comes first. Every number in your answer is automatically checked against the results of your analyse, run_sql and calculate calls, and any figure that does not match is flagged to the user as unverified.

How to work:
- For questions about the uploaded data, never estimate or recall numbers. A whole-table figure that <tables> already lists (a column's sum, min or max, the number of rows, a date range, the list of values) is computed exactly by the app: answer it directly from there, without a tool. Anything filtered, grouped, compared or derived comes from a tool.
- Use analyse for totals, counts, averages, lowest/highest values and breakdowns (by party, item, month, FY...), with filters and top N. It works on exact decimals and checks that the groups add up to the overall total. Use run_sql only for what analyse cannot express, such as joins between tables, listing individual rows, or calculations across the columns of each row.
- When you need several figures, ask for all the tool calls in the same step: they run in parallel, and every extra step makes the person wait about two seconds.
- Compute derived figures (differences, shares, growth) with the calculate tool or in SQL, never in your head.
- Check which columns hold what before relying on them: the data dictionary in <tables> lists each column's header in the file, its role, its range or exact values, and notes from importing the file. Match text filters to the exact values listed there.
- If a question is ambiguous in a way that changes the numbers (for example "sales" could be a Sales category or the Credit column), state the interpretation you used; if no reasonable interpretation stands out, ask one short clarifying question instead of guessing.
- analyse already proves that its groups add up to the overall total, so one analyse call is enough for a breakdown. When a money figure comes from run_sql, cross-check it against analyse or the column sum in <tables>; if they disagree, investigate before answering.
- SQL is DuckDB: wrap table and column names in double quotes. Number columns are exact DECIMALs. Date columns are DATE values: filter with "date" >= DATE '2026-04-01' and group with strftime("date", '%Y-%m') or date_trunc('month', "date"). Text comparisons are case-sensitive, so compare lower(trim("col")). Empty amounts are NULL; SUM ignores them.
- If a query fails or returns something unexpected, read the error or result, fix the query and try again.
- For questions about how columns relate (which formula produces a column), propose candidate formulas from the column names, sample rows and domain knowledge (for example in jewellery 1 carat = 0.2 g, fine weight = net weight × tunch / 100; in GST tax = taxable value × rate / 100), then test each with check_formula on every row. State a formula as fact only when it matches all rows (or say exactly which rows break it and by how much). For a column that is always empty, look at related columns for the reason and say how sure you are.
- General accounting questions (for example what a GST input credit is) can be answered directly without querying.
- If the data cannot answer the question, say so and say what is missing rather than guessing.

How to answer:
- Start with the direct answer in one or two sentences, then add a short breakdown (a list or a small Markdown table) only when it helps.
- Copy figures exactly as the tools returned them, formatted with Indian digit grouping and two decimals for money (11,81,251.00; 1,06,32,762.45). Only name a currency if the data shows one.
- Do not include SQL in the answer; the app shows the queries separately."""

REPAIR_PROMPT = (
    "Accuracy check: these figures in your answer do not match any analyse, run_sql or calculate result: {figures}. "
    "Recompute each of them with analyse, run_sql or calculate, then reply with the complete corrected answer. "
    "The user will see only this new answer."
)


class LLMError(Exception):
    """A chat request failed. ``message`` is safe to show to the user."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class Cancelled(BaseException):
    """The person stopped the answer or closed the app. A BaseException (like asyncio.CancelledError), so the
    catch-alls that turn tool failures into messages for the model let it through."""


class CancelEvent(threading.Event):
    """Set when an answer is cancelled. Setting it also closes whatever is registered with ``closing`` (the
    open model stream), on a separate thread so the caller never waits on a network close."""

    def __init__(self):
        super().__init__()
        self._closers: list[Callable[[], None]] = []
        self._closers_lock = threading.Lock()

    def set(self) -> None:
        super().set()
        with self._closers_lock:
            closers, self._closers = self._closers, []
        if closers:
            threading.Thread(target=_close_all, args=(closers,), daemon=True).start()

    @contextmanager
    def closing(self, close: Callable[[], None]):
        """Run ``close`` if the answer is cancelled while this block runs."""
        with self._closers_lock:
            self._closers.append(close)
        try:
            if self.is_set():
                raise Cancelled()
            yield
        finally:
            with self._closers_lock:
                if close in self._closers:
                    self._closers.remove(close)


def _close_all(closers: list[Callable[[], None]]) -> None:
    for close in closers:
        try:
            close()
        except Exception:  # noqa: BLE001 - the stream is being abandoned either way
            pass


def closing_on_cancel(cancel: threading.Event | None, close: Callable[[], None]):
    return cancel.closing(close) if isinstance(cancel, CancelEvent) else nullcontext()


# Answers a provider writes itself when the model did not finish. They are shown, but never cached or
# accepted as a correction.
NEEDS_MORE_STEPS = "The analysis needed more steps than allowed. Try a narrower question."
DECLINED = "The model declined to answer this question. Try rephrasing it."
NO_ROOM = "The model ran out of room before answering. Try a narrower question."
EMPTY_ANSWER = "The model returned an empty answer."
CUT_OFF_NOTE = "\n\n(The answer was cut off because it was too long.)"


def is_fallback(answer: str) -> bool:
    return answer.strip() in (NEEDS_MORE_STEPS, DECLINED, NO_ROOM, EMPTY_ANSWER, "") or answer.endswith(CUT_OFF_NOTE)


@dataclass
class Reply:
    """A model's answer. ``complete`` is False when the model did not finish (refused, cut off, empty, out of
    steps). ``transcript`` is the exchange in the provider's own format, tool calls and results included, so a
    correction round can continue it instead of querying everything again."""

    text: str
    model: str
    complete: bool = True
    transcript: list = field(default_factory=list)


def tool_error(exc: Exception) -> str:
    """What the model is told when a tool call fails: the real reason, so it can correct the call."""
    # Most specific first: AnalysisError, CalcError and EditError are ValueErrors, and so is JSONDecodeError.
    if isinstance(exc, QueryError):
        return f"SQL error: {exc}"
    if isinstance(exc, analysis.AnalysisError):
        return f"Analyse error: {exc}"
    if isinstance(exc, CalcError):
        return f"Calculation error: {exc}"
    if isinstance(exc, EditError):
        return f"Error: {exc}"
    if isinstance(exc, RecursionError):
        return "Error: the expression is too long or nested too deeply. Split it into smaller steps."
    if isinstance(exc, (json.JSONDecodeError, KeyError, TypeError)):
        return f"Error: the arguments do not match the tool's parameters ({type(exc).__name__}: {exc})."[:600]
    return f"Error: the tool failed ({type(exc).__name__}: {exc})."[:600]


_ROLE_TEXT = {
    "date": "the main transaction date",
    "amount": "the main amount column",
    "debit": "the debit column",
    "credit": "the credit column",
    "category": "the main grouping column (account / party / category)",
}
_MAX_LISTED_VALUES = 30
_REGISTER_TEXT = {
    "sales": "This is the SALES register: invoices to customers. Its GST is output tax; its parties are customers (receivables).",
    "purchases": "This is the PURCHASE register: bills from suppliers. Its GST is input tax credit; its parties are suppliers "
                 "(payables). When comparing with sales, compare taxable values (excluding GST) unless asked otherwise.",
}


def _column_line(table: str, col: dict, roles: dict[str, str]) -> str:
    """One data-dictionary line: name, type, header in the file, role and value range or list."""
    parts = [f'{quote_ident(col["name"])} {col["kind"]}']
    if col["label"] != col["name"]:
        parts.append(f'header in file "{col["label"]}"')
    if col["name"] in roles:
        parts.append(roles[col["name"]])
    stats = col.get("stats") or {}
    if col["non_null"] == 0:
        parts.append("always empty")
        return "  " + "; ".join(parts)
    if col.get("role") == "identifier":
        parts.append("reference number, do not add up")
    elif col["kind"] == "number" and "min" in stats:
        parts.append(f'min {stats["min"]}, max {stats["max"]}, sum {stats["sum"]}')
        if stats.get("negatives"):
            parts.append(f'{stats["negatives"]} negative values')
    elif col["kind"] == "date" and "min" in stats:
        parts.append(f'from {stats["min"]} to {stats["max"]}')
    elif col["kind"] == "text" and 0 < col["unique"] <= _MAX_LISTED_VALUES:
        values = run_select(
            f'SELECT DISTINCT {quote_ident(col["name"])} FROM {quote_ident(table)} '
            f'WHERE {quote_ident(col["name"])} IS NOT NULL ORDER BY 1',
            {table},
            limit=_MAX_LISTED_VALUES,
        ).rows
        parts.append("all values: " + ", ".join(repr(row[0]) for row in values))
    elif col["kind"] == "text":
        parts.append(f'{col["unique"]} distinct values')
    if col["nulls"]:
        parts.append(f'{col["nulls"]} empty')
    return "  " + "; ".join(parts)


def _describe_sheet(sheet: dict) -> str:
    profile = sheet["profile"]
    detected = profile.get("summary", {}).get("detected", {})
    roles = {col: _ROLE_TEXT[role] for role, col in detected.items() if role in _ROLE_TEXT and col}
    for col in detected.get("tax", []):
        roles[col] = "a tax column"
    lines = [
        f'Table {quote_ident(sheet["table_name"])} (sheet "{sheet["sheet_name"]}", {sheet["row_count"]} rows)',
        *([_REGISTER_TEXT[sheet["register"]]] if sheet.get("register") in _REGISTER_TEXT else []),
        "Columns:",
        *(_column_line(sheet["table_name"], col, roles) for col in profile["columns"]),
    ]
    checks = profile.get("checks", [])
    if checks:
        lines.append("Notes from importing the file:")
        lines += [f'  - {c["message"]}' for c in checks]
    if profile.get("user_notes"):
        lines.append(f'Notes from the user about this sheet: {profile["user_notes"]}')
    sample = read_preview(sheet["table_name"], SAMPLE_ROWS)
    lines.append("Sample rows:")
    lines.append(sample.to_json(orient="records", date_format="iso", force_ascii=False))
    return "\n".join(lines)


class _Memo:
    """A small least-recently-used memory of values that are slow to build (seconds on big sheets). A caller
    asking for a value another thread is building waits for it instead of building it again."""

    def __init__(self, size: int):
        self.size = size
        self._values: OrderedDict = OrderedDict()
        self._building: dict[tuple, threading.Event] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple, build: Callable[[], object]):
        while True:
            with self._lock:
                if key in self._values:
                    self._values.move_to_end(key)
                    return self._values[key]
                building = self._building.get(key)
                if building is None:
                    self._building[key] = threading.Event()
                    break
            building.wait()  # then read it, or build it here if that build failed
        try:
            value = build()
            with self._lock:
                self._values[key] = value
                while len(self._values) > self.size:
                    self._values.popitem(last=False)
            return value
        finally:
            with self._lock:
                self._building.pop(key).set()


# Each sheet's description runs DISTINCT and preview queries; it only changes when the sheet does.
_DESCRIPTIONS = _Memo(64)


def describe_tables(sheets: list[dict]) -> str:
    """A data dictionary for every sheet: column meanings, value ranges, data checks and sample rows."""
    return "\n\n".join(
        _DESCRIPTIONS.get((*sheet_key(sheet), sheet["sheet_name"], sheet.get("register")), lambda s=sheet: _describe_sheet(s))
        for sheet in sheets
    )


REGISTERS_TABLE_TEXT = (
    'Table "registers" (both registers together, one row per register row, amounts in rupees): '
    'register (\'Sales\' or \'Purchases\'), date, party, invoice_no, gstin, item, taxable, cgst, sgst, igst, cess, gst '
    "(total GST), invoice_value. Use it to compare sales with purchases, e.g. analyse taxable by register and month."
)


DOCUMENTS_GUIDE = """<documents> says what each file the person shared is, as detected by the app from the data, with the evidence. When files have just been shared (or the person asks what they are), explain each file in its own short section: what it is (sales register, purchase register, bank statement, ledger), the evidence in plain words, its period, the number of entries and one or two key totals from <tables>. If a detection has low confidence or evidence points both ways, say so and ask the person to confirm.

When there is a sales register and a purchase register, <combined> holds the app's exact comparison of the two. After the files are shared, keep the per-file part short (one line each: which file is the sales register, which the purchase register, and why), then analyse the two together under clear headings:
1. Sales vs purchases: taxable value, GST and invoice value of each, the difference and the margin on sales (say it is before opening/closing stock and expenses).
2. GST: output tax, input tax credit, what is payable in cash after set-off (by head) and any credit carried forward.
3. Month by month: a small Markdown table of sales, purchases and the difference.
4. Items bought vs sold (and quantities or weights left) and parties who are both customer and supplier, when <combined> has them.
5. Two or three short observations or things to check, from the figures and the notes.
Figures in <combined> are exact: quote them as written, without tools. For later questions that involve both files, use the "registers" table (both registers together) or <combined>."""


def build_instructions(sheets: list[dict], registers: bool = False, documents: str | None = None) -> tuple[str, str]:
    """(instructions for the model, the data dictionary alone). Figures in the dictionary are computed by the
    app, so an answer may quote them directly; the dictionary is also what those answers are checked against."""
    tables = describe_tables(sheets) + (f"\n\n{REGISTERS_TABLE_TEXT}" if registers else "")
    instructions = f"{SYSTEM_PROMPT}\n\n<tables>\n{tables}\n</tables>"
    if documents:
        instructions += f"\n\n{DOCUMENTS_GUIDE}\n\n<documents>\n{documents}\n</documents>"
        tables += f"\n\n{documents}"
    return instructions, tables


FORMULA_TOOL_DESCRIPTION = (
    "Test whether a column equals a formula of other columns on every row of a table. Returns how many rows match "
    "within the tolerance and examples of rows that do not. Use it to establish or verify how columns relate."
)
FORMULA_PARAMS = {
    "table": "The table name, e.g. ds2_sheet1.",
    "target_column": "The column the formula should reproduce, e.g. fine.",
    "expression": "Formula over column names, e.g. net_wt * tunch / 100 or gr_wt - (dia_wt + stn_wt) * 0.2. "
                  "Allowed: + - * / brackets % round abs min max; blank cells count as 0.",
    "tolerance": "Largest difference still counted as a match, e.g. 0.001 for weights or 1 for rupee amounts.",
}


_ROWIDS = _Memo(16)


def _formula_frame(sheet: dict) -> pd.DataFrame:
    """The sheet as check_formula reads it, from the prepared-table memory instead of a full reload from SQLite:
    numbers as floats, dates as datetimes, plus the rowids its examples refer to."""
    frame = prepare_sheet(sheet)[0]

    def rowids():
        with engine.connect() as conn:
            return pd.read_sql_query(f'SELECT rowid FROM {quote_ident(sheet["table_name"])} ORDER BY rowid', conn)["rowid"].to_numpy()

    ids = _ROWIDS.get(sheet_key(sheet), rowids)
    if len(ids) != len(frame):  # changed in between: read it afresh
        return load_frame(sheet)
    return frame.assign(**{ROWID: ids})


_WARMED = _Memo(32)


def warm_tables(sheets: list[dict], extra: dict | None = None) -> None:
    """Prepare the DuckDB tables a chat will query (seconds on big sheets), e.g. as soon as files are shared.
    A chat opening its session meanwhile waits for this work instead of doing it a second time."""
    extra_keys = tuple(sorted((name, str(frame.attrs.get("cache_key"))) for name, (frame, *_rest) in (extra or {}).items()))
    key = (tuple(sheet_key(s) for s in sheets), extra_keys)
    _WARMED.get(key, lambda: Session(sheets, extra).close())


@dataclass
class Toolbox:
    """The model's tools for one upload, with a log of every call to show the user and to verify answers."""

    sheets: dict[str, dict] = field(default_factory=dict)  # table name -> sheet
    extra: dict | None = None  # extra DuckDB tables, e.g. both registers of a sales + purchase set
    queries: list[dict] = field(default_factory=list)
    calculations: list[dict] = field(default_factory=list)
    formula_checks: list[dict] = field(default_factory=list)
    analyses: list[dict] = field(default_factory=list)
    # Live progress for the person waiting: {"type": "step", "text": ...} after each tool call.
    emit: Callable[[dict], None] = lambda _event: None
    # Set when the person stops the answer: every further tool call raises Cancelled.
    cancel: threading.Event | None = None
    _session: Session | None = None
    # Tool calls may run in parallel; one DuckDB connection must not, so queries take turns (each takes ms).
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _closed: bool = False

    @property
    def cache_key(self) -> str:
        """Same tables -> same key, so OpenAI keeps serving the long instructions from its prompt cache."""
        return "accountsai-" + hashlib.sha1(",".join(sorted(self.sheets)).encode()).hexdigest()[:16]

    def check_cancelled(self) -> None:
        if self.cancel is not None and self.cancel.is_set():
            raise Cancelled()

    def session(self) -> Session:
        """One DuckDB session per chat request, opened on first use. Call with self._lock held."""
        if self._session is None:
            if self._closed:
                raise QueryError("This chat has finished.")
            warm_tables(list(self.sheets.values()), self.extra)
            self._session = Session(list(self.sheets.values()), self.extra)
        return self._session

    @contextmanager
    def _connection(self):
        """The session, for one tool call at a time; a query still running when the answer is stopped is
        interrupted. Once the chat has closed, the last user closes it."""
        try:
            with self._lock:
                session = self.session()
                with closing_on_cancel(self.cancel, session.conn.interrupt):
                    yield session
        finally:
            self._close_if_finished()

    def _close_if_finished(self) -> None:
        # Called after releasing the lock: close() may have run while it was held and could not close then.
        if self._closed and self._lock.acquire(blocking=False):
            try:
                if self._session is not None:
                    self._session.close()
                    self._session = None
            finally:
                self._lock.release()

    def prepare(self) -> None:
        """Open the session in the background while the model reads the question."""
        try:
            with self._connection():
                pass
        except (Exception, Cancelled):  # noqa: BLE001 - the first real tool call reports any problem
            pass

    def close(self) -> None:
        """Finish the chat without waiting for a tool call (or the background prepare) still holding the session."""
        self._closed = True
        self._close_if_finished()

    def analyse(self, spec: dict) -> str:
        """Run an analysis; return a compact JSON result for the model. Raises AnalysisError (already logged)."""
        self.check_cancelled()
        try:
            with self._connection() as session:
                result = analysis.run(session, spec)
        except (analysis.AnalysisError, QueryError) as exc:
            self.analyses.append({"spec": spec, "error": str(exc)})
            self.emit({"type": "step", "text": "Adjusting the analysis…"})
            raise
        self.analyses.append({**result, "error": None})
        self.emit({"type": "step", "text": f"Analysed: {result['description']}"})
        # The checked figures can be shown at once, before the model has written its sentence.
        self.emit({"type": "analysis", "result": result})
        return json.dumps({
            "description": result["description"],
            "columns": [{"key": c["key"], "label": c["label"]} for c in result["columns"]],
            "rows": result["rows"][:ROWS_SHOWN_TO_MODEL],
            "more_rows": max(0, len(result["rows"]) - ROWS_SHOWN_TO_MODEL),
            "total": result["total"],
            "rows_matched": result["rows_matched"],
            "groups": result["groups"],
            "checks": [c["message"] for c in result["checks"]],
        }, default=str)

    def check_formula(self, table: str, target_column: str, expression: str, tolerance: float) -> str:
        """Run a formula check. Raises EditError/CalcError (already logged) on failure."""
        from ..editing import check_formula

        self.check_cancelled()
        try:
            if table not in self.sheets:
                raise EditError(f"Unknown table {table!r}; use one of {sorted(self.sheets)}.")
            result = check_formula(self.sheets[table], target_column, expression, tolerance, _formula_frame(self.sheets[table]))
        except Exception as exc:
            self.formula_checks.append({"table": table, "target": target_column, "expression": expression,
                                        "error": str(exc) if isinstance(exc, (EditError, CalcError)) else tool_error(exc)})
            raise
        self.formula_checks.append({"table": table, **result, "error": None})
        self.emit({"type": "step", "text": f"Checked {target_column} = {expression} on every row"})
        return json.dumps(result)

    def calculate(self, expression: str) -> str:
        """Return the exact result as text. Raises CalcError (already logged) on failure."""
        self.check_cancelled()
        try:
            result = format_decimal(evaluate_number(expression))
        except Exception as exc:
            self.calculations.append({"expression": expression, "result": None,
                                      "error": str(exc) if isinstance(exc, CalcError) else tool_error(exc)})
            raise
        self.calculations.append({"expression": expression, "result": result, "error": None})
        self.emit({"type": "step", "text": f"Calculated {expression} = {result}"})
        return result

    def result_rows(self) -> list[list]:
        """Every value the tools returned, for answer verification."""
        rows = [row for q in self.queries for row in q.get("rows", [])]
        rows += [[c["result"]] for c in self.calculations if c["result"] is not None]
        for a in self.analyses:
            if not a.get("error"):
                rows += [list(r.values()) for r in a["rows"]]
                rows += [list((a["total"] or {}).values()), [a["rows_matched"], a["groups"]]]
        for check in self.formula_checks:
            if not check.get("error"):
                rows.append([check["rows_checked"], check["rows_blank"], check["matches"], check["mismatches"],
                             check["max_difference"], check["tolerance"]])
                rows += [[e["actual"], e["expected"], e["difference"], e["row"]] for e in check["examples"]]
        return rows

    def run_sql(self, query: str) -> str:
        """Return the result as JSON for the model. Raises QueryError (already logged) on failure."""
        self.check_cancelled()
        try:
            with self._connection() as session:
                result = session.query(query)
        except QueryError as exc:
            self.queries.append({"sql": query, "error": str(exc)})
            self.emit({"type": "step", "text": "Fixing a query…"})
            raise
        self.queries.append({"sql": query, **result.as_dict()})
        self.emit({"type": "step", "text": f"Ran a query ({result.as_dict()['row_count']} rows)"})
        shown = result.rows[:ROWS_SHOWN_TO_MODEL]
        return json.dumps(
            {
                "columns": result.columns,
                "rows": shown,
                "rows_returned": len(shown),
                "more_rows_available": result.truncated or len(result.rows) > len(shown),
            },
            default=str,
        )
