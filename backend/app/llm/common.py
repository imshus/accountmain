"""Pieces every chat model shares: the instructions, the table context and the tools (analyse, SQL, calculate)."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import OrderedDict
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import func, select, text

from .. import analysis, cloud, detect
from ..accounts import imports as books_imports
from ..accounts.service import AccountsError
from ..calc import CalcError, evaluate_number, format_decimal
from ..accounts.db import ledgers as books_ledgers
from ..accounts.db import metal_lines as books_metal_lines
from ..accounts.db import voucher_lines as books_voucher_lines
from ..accounts.db import vouchers as books_vouchers
from ..database import QueryError, engine, get_dataset, quote_ident, read_preview
from ..duck import Session, prepare_sheet, sheet_frame, sheet_key
from ..editing import EditError, load_frame

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

Adding to the books:
- The app itself reads, in any language, whether the person's latest message asks to add a shared file or a bill they typed to sales or purchases, and adds it: shared files before you answer (listed in <added>), a typed bill through add_bill, which you are given only when they asked. Never ask them to confirm and never ask "sales or purchase?"; ask only for what <needs> lists (a file's missing date or customer / supplier). Never say something was added that <added> or add_bill does not show.
- For each file in <added>, say in the person's language how many entries were added and how many were already in the books, exactly as given, and its problems briefly (what went wrong, and how many problems in all), without row numbers. Never invent counts. Its notes say when to add one short line: the register the app chose from the file (and why), a file that looks like the other register, the books-start date moved, bills dated today or put under a customer or supplier because the file had none, or total rows left out (with their count; they are not problems).
- When <documents> lists shared files as "Not in the books yet" and nothing was added, end with ONE short line in the person's language offering to add them, e.g. "Isko Sales ya Purchase me add karna ho to neeche button dabayein ya likh dein."; the app shows Sales and Purchase buttons under it.

Follow-up questions:
- An earlier answer may end with a <context> block listing the tool calls that produced it. A short follow-up ("aur Garg ka?", "overall?", "June me?", "month-wise", "iska GST?", "and for purchases?") continues the latest question: keep its table, measure, filters and period, and change only what the new question changes. Another party or item: swap that filter value, matched to the exact values in <tables>. Drop the party or item filter only when the person asks for everyone ("overall", "sab parties", "sabka", "all items", "baaki sab bhi"); "total", "sab" or "all" on their own keep the current filters and period ("iska total GST?" is still the same party and period). "X-wise": add that grouping. A new period: change only the date filter.
- If a name in a follow-up is not among the exact values listed in <tables>, find the exact value first (analyse with a contains filter, or SELECT DISTINCT with lower(...) LIKE). A filter that matched no rows means the name was not found: say so, never report it as 0.
- Recompute with the tools: earlier answers are context, not evidence. Never write a <context> block yourself.

Accounting principles:
- Apply Indian accounting principles and standards (AS; companies on Ind AS follow the Ind AS equivalents) to interpret the data, never to change it: give a figure as recorded and, separately, the rows and amount a principle would treat differently (an advance, goods on approval, a personal payment, credit that may be blocked). Every figure still comes from <tables> or a tool.
- A principle question about the uploaded data (it names a party, bill, date or column in it, or a charge a column holds, such as making charges in a Lbr., Labour or Making column): look those rows up with a tool and conclude for them with their amounts (which bill falls in which period; whether the file's making charges are on sales, so output tax and part of the jewellery's value, or on purchases, so input credit). Name the deciding principle briefly, in the reply's language (e.g. on accrual basis a 28 March invoice belongs to FY 2025-26 even if paid in April).
- Accrual and matching: income and expenses belong to the period in which they are earned or incurred, not when cash moves; a bank statement or cash book shows cash movements, so report its receipts and payments as such. Periods are Indian financial years (April to March) unless the person says otherwise; a plain year ("2025 me") may mean FY 2025-26 or calendar 2025, so say which you used. Sales minus purchases is not profit: profit also needs opening and closing stock and expenses.
- Revenue (AS 9): a sale counts when the property in the goods, or their significant risks and rewards, pass to the buyer, usually on delivery or invoicing; an advance received before that is a liability. Goods on approval stay in stock until the buyer accepts them or the time to return them passes.
- Prudence: anticipate no profit, provide for known losses. Book stock is at the lower of cost and net realisable value (AS 2), never at a metal rate or selling price above cost. Cost excludes GST taken as credit and is the specific cost of unique pieces, or FIFO or weighted average for interchangeable items (never LIFO). A value at today's rate (given by the person or in the data) is a market value: give it when asked, labelled so, not as book stock or profit.
- Double entry: each voucher's debits equal its credits, and so do a trial balance's totals. A party ledger or bank statement need not balance: its difference is the balance. A sheet with only one side of the entries (e.g. sales credits and expense debits, no bank, cash or party side) cannot tally: say so plainly; its difference is their net, not an error.
- Consistency and materiality: compare periods on the same basis. A difference may be called small (e.g. rounding), but give its exact amount and rows; never drop, round or net off a figure because it is small. Entity: the owner's personal receipts and payments are capital or drawings, not income or expense.
- GST on sales is output tax. GST on purchases is input tax credit (ITC) if section 16 is met (tax invoice, goods or services received, invoice in GSTR-2B, tax paid to the government by the supplier, own return filed, supplier paid within the time allowed, credit taken in time) and section 17(5) does not block it (e.g. cars for own use, food and drinks, gifts, free samples, goods lost or written off, subject to its exceptions). A register cannot show these conditions: report its total as GST on purchases (ITC as per the register), never reduced by you. Reverse-charge tax (often on a transporter's freight or an advocate's fees) is paid in cash, never from credit, then taken as credit if eligible. IGST credit is used first, against IGST, then CGST or SGST; CGST and SGST credit never pay each other.
- Supplier's location and place of supply in the same state or union territory: CGST + SGST (UTGST in a union territory without a legislature); in different states, and for exports, imports and supplies to or by an SEZ unit: IGST. For goods the place of supply is generally where the movement ends; for an unregistered buyer, the state of the address on the invoice (the shop's when none is recorded). The business's state is the first two digits of its GSTIN; if the data does not show it, infer it from the GSTINs of the parties charged CGST + SGST, say so, and conclude instead of leaving the answer conditional.
- Jewellery: making charges billed with jewellery are part of its taxable value, so GST on them is output tax, not input credit. Asked about input credit on making charges when the data has a making-charge column on sale rows: say first that the file's making charges are on sales (with their total from a tool), so they carry output tax and give no credit; credit is only on making charges the business pays (a karigar's or job worker's invoice), if eligible. Making jewellery from a customer's own metal is a separate service, job work only if the customer is registered: take its rate from the data.
- Flag entries that may break a principle, with their rows and amounts from the tools, and say why: a voucher whose debits and credits differ; GST credit on an item that looks blocked (it may fall under an exception); a sale whose delivery or approval date in the data falls after the period it is booked in; negative stock.
- Rates, limits and section numbers change (many GST rates from 22 September 2025; the Income-tax Act, 2025, renumbered, from 1 April 2026). A rate worked out from the data (a rate column, or tax / taxable value × 100 with calculate) is the rate charged on those invoices, not proof of the legal rate: say so, and when similar items carry different rates or the rate changes around 22 September 2025, point it out and suggest checking the classification with a CA. If a general question needs a legal rate, limit or threshold the data cannot show, say the data does not show it, state the rule in words (e.g. TDS on purchases of goods applies to buyers above a turnover limit) and suggest checking the current notification or a CA. Never quote a rate, limit or threshold from memory, or run calculate on a number not from the data.

How to answer:
- Answer in the language and script of the user's latest message: Hinglish stays Hinglish in Latin script, Hindi in Devanagari stays Devanagari, English stays English.
- Start with the direct answer in one or two sentences, then add a short breakdown (a list or a small Markdown table) only when it helps.
- Copy figures exactly as the tools returned them, formatted with Indian digit grouping and two decimals for money (11,81,251.00; 1,06,32,762.45). Write amounts without a currency sign (11,81,251.00, not ₹11,81,251.00) unless a column header or value in <tables> shows one (₹, Rs, INR); amounts the person typed without one stay without one.
- Do not include SQL in the answer; the app shows the queries separately."""

REPAIR_PROMPT = (
    "Accuracy check: these figures in your answer do not match any analyse, run_sql or calculate result: {figures}. "
    "Recompute each of them with analyse, run_sql or calculate, then reply with the complete corrected answer. "
    "The user will see only this new answer: write it as a first reply, without mentioning the check, a correction or an earlier draft."
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


# The app sends each earlier answer back followed by a <context> block of the tool calls behind it. A block the model
# copies into its own answer (even one cut off before its closing tag) is removed, so it is never shown or kept. Only a
# block whose opening tag stands on a line of its own counts: a sentence that mentions <context> is left alone.
_CONTEXT_BLOCK = re.compile(
    r"\s*^[ \t]*<context>[ \t]*$.*?(?:</context>|\Z)"  # a block, through its closing tag or the end of the text
    r"|\s*</?context\b[^>]*\Z"  # a tag cut off at the very end
    r"|\s*^[ \t]*</context>[ \t]*\Z",  # the closing tag alone on the last line
    re.S | re.M,
)


def strip_context(text: str) -> str:
    """``text`` without <context> blocks; the note on a cut-off answer stays at the end."""
    note = CUT_OFF_NOTE if text.endswith(CUT_OFF_NOTE) else ""
    body, removed = _CONTEXT_BLOCK.subn("", text[:len(text) - len(note)])
    return body.strip() + note if removed else text


# Words only Hinglish uses; not "me", "to" or "so", which English has too.
_HINGLISH = frozenset(
    "kya kitna kitni kitne hai hain aur ka ki ke ko mein batao dikhao sabse kaun kis kaunsa dono wala wali hua hui "
    "iska uska inka unka nahi".split()
)
_DEVANAGARI = re.compile(r"[\u0900-\u0963\u0971-\u097f]")  # letters and vowel signs, not the digits or the danda


def reply_language(messages: list[dict]) -> str | None:
    """The language of the person's latest message, so the reply (and the suggested questions) can be told to use it
    rather than the language of earlier answers. A message without letters ("?") takes the one before it; None when
    no message says (or it is in another script)."""
    for message in reversed(messages):
        if message["role"] != "user":
            continue
        text = strip_context(message["content"])
        if _DEVANAGARI.search(text):
            return "Hindi (Devanagari script)"
        words = re.findall(r"[a-z]+", text.lower())
        if any(word in _HINGLISH for word in words):
            return "Hinglish (Hindi in Latin script)"
        if words:
            return "English"
        if any(ch.isalpha() for ch in text):
            return None
    return None


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
    # Most specific first: AnalysisError, CalcError, EditError and AccountsError are ValueErrors, and so is JSONDecodeError.
    if isinstance(exc, QueryError):
        return f"SQL error: {exc}"
    if isinstance(exc, analysis.AnalysisError):
        return f"Analyse error: {exc}"
    if isinstance(exc, CalcError):
        return f"Calculation error: {exc}"
    if isinstance(exc, (EditError, AccountsError)):
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


def _listed_values(sheet: dict, column: str) -> list[str]:
    """A text column's distinct values in code-point order (as SQLite's ORDER BY gave them; a Postgres collation would
    order them differently), at most _MAX_LISTED_VALUES, from the sheet's table already in memory: no query per column."""
    values = sheet_frame(sheet)[column].dropna().unique()
    return sorted(str(v) for v in values)[:_MAX_LISTED_VALUES]


def _column_line(sheet: dict, col: dict, roles: dict[str, str]) -> str:
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
        parts.append("all values: " + ", ".join(repr(value) for value in _listed_values(sheet, col["name"])))
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
        *(_column_line(sheet, col, roles) for col in profile["columns"]),
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


# Each sheet's description reads its table and its first rows; it only changes when the sheet does.
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


def build_instructions(sheets: list[dict], registers: bool = False, documents: str | None = None,
                       books: bool = False, books_note: str = "") -> tuple[str, str]:
    """(instructions for the model, the data dictionary alone). Figures in the dictionary are computed by the
    app, so an answer may quote them directly; the dictionary is also what those answers are checked against.
    ``books``: the company's books tables are there too (llm/books_data.py); ``books_note`` says which of them could
    not be read this time (books_data.unreadable_note), so an empty one is not taken for empty books."""
    from .books_data import BOOKS_TABLES_TEXT  # books_data imports the accounts package, which is heavier

    books_text = "\n".join(part for part in (BOOKS_TABLES_TEXT, books_note) if part) if books else ""
    tables = "\n\n".join(part for part in (describe_tables(sheets), REGISTERS_TABLE_TEXT if registers else "",
                                           books_text) if part)
    from datetime import date as _date

    instructions = f"{SYSTEM_PROMPT}\n\n<tables>\n{tables}\n</tables>"
    if documents:
        instructions += f"\n\n{DOCUMENTS_GUIDE}\n\n<documents>\n{documents}\n</documents>"
        tables += f"\n\n{documents}"
    # Last, so everything above stays the same from day to day: "aaj ki sale" needs the date, which the model cannot know.
    today = _date.today()
    instructions += f"\n\nToday is {today:%A, %d %B %Y} ({today.isoformat()})."
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

BOOKS_REGISTERS = ("sales", "purchases")
_PROBLEMS_SHOWN_TO_MODEL = 10
# The upload's warnings about the sheet's own reports when it has no date or party column: untrue of the books once the
# chat's add has given each bill a date and a party (its notes say which), so not passed on.
_SHEET_REPORT_NOTE = re.compile(r"no (date|customer/supplier) column chosen")


def _books_start_note(moved: dict) -> str:
    return (f"The books began on {moved['from']:%d/%m/%Y}; they now begin on {moved['to']:%d/%m/%Y} (the start of the "
            "financial year of the earliest bill), so the bills fit. Say so in one short line.")


# The customer or supplier of a bill that names none: a walk-in, kept on one ledger, so the bill is still posted.
CASH_PARTY = {"sales": "Cash Customer", "purchases": "Cash Supplier"}
# This share of a sheet's codes found in another sheet of the same file: the same items listed twice.
_SAME_ITEMS = 0.8


# A column of row numbers ("S.No", "Sr. No."): its 1, 2, 3 are in every sheet and say nothing about the items.
_SERIAL_COLUMN = re.compile(r"^(s|sr|sl|serial|sn|sno|srno|slno)(_?no|_?num|_?number)?$")
# Columns naming a party, not an item or a bill: the same shops are billed every month.
_PARTY_ID_COLUMN = re.compile(r"(^|_)(gstin|gst|gst_no|gstin_no|pan|phone|mobile|contact|party|customer|supplier|vendor|"
                              r"client|buyer|seller|ledger|account|name)(_|$)")
_GSTIN_VALUE = re.compile(r"^\d{2}[a-z]{5}\d{4}[a-z][0-9a-z]z[0-9a-z]$")
# Columns naming a period (Apr-26, Q1, 2026), as a summary by month has: not item or bill codes.
_PERIOD_COLUMN = re.compile(r"(^|_)(month|period|year|quarter|week|fy|financial_year)(_|$)")
# Columns naming an item's kind ("Ring 22K", "Chain"), not one item: never codes.
_LABEL_COLUMN = re.compile(r"(^|_)(item|items|item_name|category|description|product|particulars|details|narration|remarks|"
                           r"metal|purity|karat|colour|color|clarity)(_|$)")
# Number columns that are codes when they are named so: barcodes, tags, design or bill numbers kept as numbers.
_CODE_NAME = re.compile(r"(^|_)(barcode|bar_code|code|tag|tag_no|huid|design|design_no|style|style_no|sku|bill|bill_no|"
                        r"invoice|invoice_no|inv_no|voucher|voucher_no|vch_no)(_|$)")


def _sheet_rows(sheet: dict) -> tuple[pd.DataFrame, dict[str, str]]:
    """(the sheet's rows, column -> kind)."""
    return load_frame(sheet), {c["name"]: c["kind"] for c in sheet["profile"]["columns"]}


def _code_columns(frame: pd.DataFrame, kinds: dict[str, str]) -> list[str]:
    """Columns that name one item or one bill (a jewel code, tag, barcode or bill number): mostly different one-word
    values with digits (TW001, S-101, 80451201); not row numbers (S.No, or 1, 2, 3...), not a party's GSTIN, phone or
    name, not a period, and not an item's name or kind ("Ring 22K"). A number column counts only when named as a code."""
    found = []
    for column, kind in kinds.items():
        if (kind not in ("text", "number") or (kind == "number" and not _CODE_NAME.search(column))
                or _SERIAL_COLUMN.match(column) or _PARTY_ID_COLUMN.search(column) or _PERIOD_COLUMN.search(column)
                or _LABEL_COLUMN.search(column)):
            continue
        values = [_code(v) for v in frame[column].dropna() if _code(v)]
        distinct = set(values)
        if (len(values) >= 2 and len(distinct) >= _SAME_ITEMS * len(values)
                and sum(any(ch.isdigit() for ch in v) for v in values) >= _SAME_ITEMS * len(values)
                and sum(" " not in v for v in values) >= _SAME_ITEMS * len(values)
                and distinct != {str(n) for n in range(1, len(distinct) + 1)}
                and sum(bool(_GSTIN_VALUE.match(v)) for v in distinct) < _SAME_ITEMS * len(distinct)):
            found.append(column)
    return found


def _code(value) -> str:
    """A code cell as text: 80451201.0 (a barcode read as a number) is 80451201."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip().lower()


def _second_columns(a: tuple, b: tuple) -> list[str]:
    """Columns both sheets have that tell their rows apart besides the code: the date when both have one (bills on other
    days are other bills, whatever their numbers), else the weights and amounts that vary from row to row, else (all
    the same) any weight or amount they share."""
    (fa, ka), (fb, kb) = a, b
    shared = [c for c in ka if c in kb and ka[c] == kb[c]]
    dates = [c for c in shared if ka[c] == "date"]
    if dates:
        return dates
    numbers = [c for c in shared if ka[c] == "number"]
    varying = [c for c in numbers if fa[c].nunique() >= 0.5 * max(1, fa[c].notna().sum())
               and fb[c].nunique() >= 0.5 * max(1, fb[c].notna().sum())]
    return varying or numbers


def _pairs(frame: pd.DataFrame, code: str, second: str) -> set[tuple]:
    """(code, the row's date / weight / amount) of every row with a code."""
    def norm(value):
        if isinstance(value, pd.Timestamp):
            return value.date().isoformat()
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return str(value).strip().lower()

    return {(str(c).strip().lower(), norm(x)) for c, x in zip(frame[code], frame[second])
            if not pd.isna(c) and str(c).strip() and not pd.isna(x)}


def repeated_sheets(sheets: list[dict], registers: dict[str, str | None]) -> dict[str, str]:
    """Sheets of one upload that only repeat the bills or items of another of its sheets going to the same register (a
    packing list and its priced copy), each mapped to the sheet added instead. A sheet is left out only when another
    one holds every one of its rows, matched on a code (jewel code, tag, bill number) AND on the date, or on a weight or
    amount; between two sheets holding the same rows, the richer one is kept (posted by fine weight, then more number
    columns). When neither holds all of the other's rows (a GST copy missing the estimates, bills to the same shops
    each month, numbers that restart each month), both are added: a bill counted twice shows in the totals, a bill left
    out does not. ``registers``: table -> the register it goes to."""
    from ..accounts import metal as books_metal

    def score(sheet: dict) -> tuple:
        columns = sheet["profile"]["columns"]
        return (books_metal.detect_jewellery(sheet) is not None, sum(c["kind"] == "number" for c in columns),
                sheet.get("position", 0))

    def holds(a: tuple, b: tuple) -> bool:
        """Sheet a holds every row of sheet b (at least two), by a shared code and a second column."""
        theirs_codes = _code_columns(*a)
        for code in (c for c in _code_columns(*b) if c in theirs_codes):
            for second in _second_columns(a, b):
                mine, theirs = _pairs(a[0], code, second), _pairs(b[0], code, second)
                if len(theirs) >= 2 and theirs <= mine:
                    return True
        return False

    groups: dict[tuple, list[dict]] = {}
    for sheet in sheets:
        groups.setdefault((sheet["dataset_id"], registers.get(sheet["table_name"])), []).append(sheet)
    repeated: dict[str, str] = {}
    for group in groups.values():
        if len(group) < 2:
            continue
        rows = {s["table_name"]: _sheet_rows(s) for s in group}
        for sheet in sorted(group, key=score):  # the poorest first: of two sheets with the same rows, it is left out
            mine = sheet["table_name"]
            other = next((o["table_name"] for o in group if o["table_name"] != mine and o["table_name"] not in repeated
                          and holds(rows[o["table_name"]], rows[mine])
                          and (not holds(rows[mine], rows[o["table_name"]]) or score(o) > score(sheet))), None)
            if other:
                repeated[mine] = other
    return repeated


# Amount columns (rupees): a summary is matched to the bills on these; pieces, rates and purity never.
_MONEY_COLUMN = re.compile(r"(^|_)(amount|amt|total|value|sales|purchases?|price|taxable|invoice_value|bill_amount)(_|$)")
# Weight columns: where a summary and the bills both have the same one, its totals must agree too.
_WEIGHT_COLUMN = re.compile(r"(^|_)(gross|net|fine|pure)(_?(wt|weight))?$")


def summary_sheets(sheets: list[dict], registers: dict[str, str | None]) -> dict[str, str]:
    """Sheets of one upload that only total the bills of its other sheets going to the same register (by month,
    category, item or customer), each mapped to the bills it totals. Only a sheet shaped like a summary is one: no
    dates, no item or bill codes, a label column (Month, Category, Item, Customer), no more rows than the bills; and
    its amount total equals the amount total of one bills sheet (with dates or codes) or of all of them, to the rupee,
    with every weight column both have equal to the gram. Posting the totals as well would count the sales twice; any
    doubt, and the sheet is added. A summary shared alone is not one of them: it is added as asked."""
    from ..reports import _NOT_AMOUNT  # weights, pieces, rates, purity: never rupees
    def total(frame: pd.DataFrame, column: str) -> float:
        return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())

    def money(kinds: dict[str, str]) -> list[str]:
        return [c for c, k in kinds.items() if k == "number" and _MONEY_COLUMN.search(c) and not _NOT_AMOUNT.search(c)]

    def weights(kinds: dict[str, str]) -> list[str]:
        return [c for c, k in kinds.items() if k == "number" and _WEIGHT_COLUMN.search(c)]

    groups: dict[tuple, list[dict]] = {}
    for sheet in sheets:
        groups.setdefault((sheet["dataset_id"], registers.get(sheet["table_name"])), []).append(sheet)
    summaries: dict[str, str] = {}
    for group in groups.values():
        if len(group) < 2:
            continue
        rows = {s["table_name"]: _sheet_rows(s) for s in group}
        # Bills have dates (a Month column of dates is a summary's label, not a bill date) or item or bill codes.
        bills = [t for t, (frame, kinds) in rows.items()
                 if any(k == "date" and not _PERIOD_COLUMN.search(c) for c, k in kinds.items()) or _code_columns(frame, kinds)]
        for table, (frame, kinds) in rows.items():
            if table in bills or not money(kinds):
                continue
            if not any((k == "text" or (k == "date" and _PERIOD_COLUMN.search(c))) and frame[c].notna().any()
                       for c, k in kinds.items()):
                continue  # no label column: not a summary by month, category, item or customer
            # A row per sheet ("Total Sales 2,80,000", "October 1,20,000"): one row equals one bills sheet's total.
            row_values = [float(v) for c in money(kinds) for v in pd.to_numeric(frame[c], errors="coerce").dropna() if v]
            matched = next((b for b in bills for c in money(rows[b][1]) if total(rows[b][0], c)
                            and any(abs(v - total(rows[b][0], c)) <= 1.0 for v in row_values)), None)
            if matched and len(frame) <= sum(len(rows[b][0]) for b in bills):
                summaries[table] = matched
                continue
            combos = [[b] for b in bills] + ([bills] if len(bills) > 1 else [])
            for combo in combos:
                size = sum(len(rows[b][0]) for b in combo)
                if len(frame) > size:
                    continue
                theirs_money = [sum(total(rows[b][0], c) for b in combo if c in rows[b][1])
                                for c in {c for b in combo for c in money(rows[b][1])}]
                same_money = any(abs(total(frame, mine) - t) <= 1.0 for mine in money(kinds) for t in theirs_money if t)
                shared_weights = [c for c in weights(kinds) if all(c in rows[b][1] for b in combo)]
                same_weights = all(abs(total(frame, c) - sum(total(rows[b][0], c) for b in combo)) <= 0.001
                                   for c in shared_weights)
                if same_money and same_weights:
                    summaries[table] = combo[0]
                    break
    return summaries


def pending_text(pending: list[dict]) -> str:
    """For <documents>: the shared sheets not in the books yet, which the answer offers to add (each {filename, sheet,
    suggestion})."""
    likely = {"sales": "likely the sales register", "purchases": "likely the purchase register"}
    return "\n".join(["Not in the books yet (the chosen company's books have nothing from these sheets yet):"]
                     + [f'- File "{p["filename"]}", sheet "{p["sheet"]}": '
                        + likely.get(p["suggestion"], "a sales or purchase register, unclear which") for p in pending])


BILL_TOOL_DESCRIPTION = (
    "Save one bill the person typed in the chat (\"Input by chat\") to the chosen company's books, as a sale or a purchase, "
    "exactly as the app's Sales / Purchase entry form does: a jewellery bill by weight, labour + diamond amounts, no GST. "
    "Call it once per bill as soon as the person asks, without asking them anything first; never guess a weight, purity "
    "or rate they did not give (null when not given: a bill without purity is saved without fine gold). A price the "
    "person gives is the bill's amount; a bill with a price needs no weight (an item that is not jewellery). Called "
    "again for the same bill with a price or purity given later, it updates that bill. Returns the bill number and "
    "amounts."
)
_BILL_FIELDS = {  # name -> (JSON type, description)
    "register": ("string", "sales for a bill to a customer, purchases for a bill from a supplier: as the person said, else "
                           "from their wording (bought from someone: purchases; sold to someone: sales), else sales."),
    "party": ("string", "Customer (sales) or supplier (purchases) the person named, as typed, in any wording or language: "
                        "\"from X\", \"X se\", \"to X\", \"X ko\", \"X ka\", \"X ke naam\", \"in X\" or \"X me\" (in X's "
                        "account); e.g. \"purchase of necklace in trpl\": trpl. Empty only when no one is named (the bill "
                        "is then a cash sale or purchase, posted to Cash)."),
    "item": ("string", "Item name, e.g. Ring, Chain, Bangle."),
    "gross_g": ("number|null", "Gross weight in grams; null when not given."),
    "purity_pct": ("number|null", "Purity / tunch in percent, e.g. 91.6 for 22K, 75 for 18K, 58.5 for 14K; null when not given "
                                  "(then the bill is saved with its weights and diamonds but no fine gold)."),
    "net_g": ("number|null", "Net weight in grams (\"nt wt\"); null to work it out as gross − diamond carats × 0.2."),
    "diamond_ct": ("number|null", "Diamond weight in carats (\"d. wt\", \"dia wt\"); null when none."),
    "diamond_rate": ("number|null", "Diamond rate in rupees per carat; null when none."),
    "labour_rate": ("number|null", "Labour rate in rupees per gram of net weight; null when none."),
    "amount": ("number|null", "The bill's total price in rupees when the person gives one, in any wording: \"price 600000\", "
                              "\"60000 me becha\", \"for ₹1,200\", \"1200 rupees\", \"total 1,00,000\", \"taxable value "
                              "100000\" (an amount given earlier in the conversation for this bill counts). It is the whole "
                              "bill, labour and diamonds included; never turn it into a rate. null when none."),
    "pieces": ("integer|null", "How many pieces or units (\"2 units\", \"3 pcs\"); null when not given."),
    "date": ("string|null", "Bill date as YYYY-MM-DD; null for today."),
    "bill_no": ("string|null", "Bill number when the person gave one; null to number it automatically."),
    "tag_no": ("string|null", "The item's tag number, e.g. DGR266; null when not given."),
    "huid": ("string|null", "Hallmark HUID, e.g. 74WZW; null when not given."),
    "color": ("string|null", "Diamond colour, e.g. GH; null when not given."),
    "clarity": ("string|null", "Diamond clarity, e.g. SI, VVS; null when not given."),
}


def bill_tool_schema() -> dict:
    """add_bill's parameters (strict: every field present, null when not given)."""
    props = {}
    for name, (kind, text) in _BILL_FIELDS.items():
        base, _, nullable = kind.partition("|")
        props[name] = {"type": [base, "null"] if nullable else base, "description": text}
    props["register"]["enum"] = list(BOOKS_REGISTERS)
    return {"type": "object", "properties": props, "required": list(_BILL_FIELDS), "additionalProperties": False}


# Imports take turns: two at once could both find a row not yet posted and post it twice.
_BOOKS_LOCK = threading.Lock()


def _formula_frame(sheet: dict) -> pd.DataFrame:
    """The sheet as check_formula reads it, from the prepared-table memory instead of a full reload from the database:
    numbers as floats, dates as datetimes, with the "_rowid" its examples refer to (kept in the prepared frame)."""
    return prepare_sheet(sheet)[0]


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
    # The company whose books add_to_books posts the shared sheets to (the app calls it when the intent check, llm/intent.py,
    # reads a request to add them); None: nothing can be added.
    company_id: int | None = None
    imports: list[dict] = field(default_factory=list)
    # The company add_bill saves typed bills to; None: the model has no such tool (given only when the intent check read
    # a request to save a typed bill).
    bill_company_id: int | None = None
    # The register the intent check read for that bill ("sales" / "purchases"); None: the person did not say, the model
    # decides from their wording.
    bill_register: str | None = None
    # Each bill add_bill saved or found: [total ₹, labour ₹, diamonds ₹, net g, gross g, fine g, diamond ct], for verification.
    bills: list[list] = field(default_factory=list)
    # Set once add_to_books is called, even if it failed: such an answer is never remembered.
    added_to_books: bool = False
    # Live progress for the person waiting: {"type": "step", "text": ...} after each tool call.
    emit: Callable[[dict], None] = lambda _event: None
    # Set when the person stops the answer: every further tool call raises Cancelled.
    cancel: threading.Event | None = None
    _session: Session | None = None
    # Tool calls may run in parallel; one DuckDB connection must not, so queries take turns (each takes ms).
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _closed: bool = False
    # add_to_books' reply per (table, register): asked again in this answer (in parallel, or in the correction round),
    # it gives the same reply instead of importing again.
    _book_replies: dict[tuple[str, str], str] = field(default_factory=dict, repr=False)

    @property
    def can_add_to_books(self) -> bool:
        return self.company_id is not None and bool(self.sheets)

    @property
    def can_add_bill(self) -> bool:
        return self.bill_company_id is not None

    def add_bill(self, register: str, party: str, item: str, gross_g: float | None = None, purity_pct: float | None = None,
                 net_g: float | None = None, diamond_ct: float | None = None, diamond_rate: float | None = None,
                 labour_rate: float | None = None, date: str | None = None, bill_no: str | None = None,
                 tag_no: str | None = None, huid: str | None = None, color: str | None = None, clarity: str | None = None,
                 amount: float | None = None, pieces: int | None = None) -> str:
        """Save one typed bill as the entry form does (POST /companies/{id}/vouchers/jewellery, gold, by weight, no GST);
        return its number and amounts as JSON for the model. With ``amount`` (the price the person typed) the bill is
        for that many rupees: the item is settled in rupees (its metal at the amount less labour and diamonds), or, with
        no weight (an item that is not jewellery), the bill is that amount alone. The same bill typed again with a price
        or purity it lacked is updated, not saved twice. Raises EditError/AccountsError on failure."""
        from datetime import date as _date

        from ..accounts import metal as books_metal
        from ..accounts import service as books_service

        self.check_cancelled()
        self.added_to_books = True  # an answer that saved a bill is never remembered
        if not self.can_add_bill:
            raise EditError("No company is chosen, so the bill cannot be saved. Ask the person to choose one in the app.")
        register = self.bill_register or register  # the register the intent check read in the person's words wins
        if register not in BOOKS_REGISTERS:
            raise EditError(f"Unknown register {register!r}; use sales or purchases.")
        known = self._chat_bill((bill_no or "").strip(), "Sales" if register == "sales" else "Purchase")
        if known:  # a bill saved from the chat, named by its number: what the person does not repeat stays as it was
            party, item, date = party or known["party"], item or known["item"], date or known["date"]
            gross_g = gross_g if gross_g is not None else known["gross_g"]
            net_g = net_g if net_g is not None else known["net_g"]
            diamond_ct = diamond_ct if diamond_ct is not None else known["diamond_ct"]
            purity_pct = purity_pct if purity_pct is not None else known["purity_pct"]
            tag_no, huid = tag_no or known["tag_no"], huid or known["huid"]
            color, clarity = color or known["color"], clarity or known["clarity"]
        party, item = (party or "").strip(), (item or "").strip()
        # Typed all in lower case on a phone ("hukum chand jewellers"): saved as a name is written. Other casing is kept.
        party, item = (party.title() if party.islower() else party), (item.title() if item.islower() else item)
        # No name given: a walk-in customer or supplier, on one ledger, so the bill is saved instead of asked about.
        party = party or CASH_PARTY[register]
        # The longest the books keep (the database refuses a longer value, where SQLite stored any length).
        if len(party) > 200:
            raise EditError("Not saved: the customer or supplier name is longer than 200 characters. Ask for the name as "
                            "it should appear in the books.")
        if len((bill_no or "").strip()) > 40:
            raise EditError("Not saved: the bill number is longer than 40 characters. Ask for the bill number as printed "
                            "on the bill.")
        if amount is not None and amount < 0:
            raise EditError("Not saved: the amount cannot be below zero. Ask for the bill's amount.")
        priced = bool(amount)
        weighed = bool(gross_g and gross_g > 0) or bool(net_g and net_g > 0)
        if not weighed and not priced:
            raise EditError("Not saved: the bill needs the net or gross weight in grams, or its amount in rupees. Ask for it.")
        if purity_pct is not None and not 0 < purity_pct <= 100:
            raise EditError("Not saved: purity must be a percent above 0 and at most 100 (e.g. 91.6 for 22K). Ask for it.")
        purity_given = bool(purity_pct) and weighed
        try:
            day = _date.fromisoformat(date) if date else _date.today()
        except ValueError as exc:
            raise EditError(f"Bad date {date!r}; use YYYY-MM-DD.") from exc
        key = (register, party.lower(), item.lower(), float(gross_g or 0), float(net_g or 0), float(diamond_ct or 0), str(day),
               (bill_no or "").strip().lower(), (tag_no or "").strip().lower())
        # The same bill asked again (Regenerate, or typed again after a stop) is found by this, not saved twice.
        source = "chat:" + hashlib.sha1(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:20]
        sales = register == "sales"
        vtype = "Sales" if sales else "Purchase"
        from ..accounts.api import JewelItemIn  # the entry form's item, with every field the posting reads

        line = JewelItemIn(
            item=item or None, purity=f"{round(purity_pct * 24 / 100)}K" if purity_given else None,
            tunch=float(purity_pct) if purity_given else None,
            gross=str(gross_g) if gross_g else None, net=str(net_g) if net_g else None, tag_no=(tag_no or "").strip().upper() or None, diamond_ct=str(diamond_ct) if diamond_ct else None,
            diamond_value=f"{float(diamond_ct) * float(diamond_rate):.2f}" if diamond_ct and diamond_rate else None,
            labour_rate=str(labour_rate) if labour_rate else None, settle="Wt", huid=huid or None, colour=color or None,
            clarity=clarity or None, pieces=int(pieces) if pieces and pieces > 0 else None).model_dump()
        amount_paise = books_service.to_paise(amount, "Amount") if priced else 0
        if priced and weighed:  # sold or bought for that price: the metal is what is left after labour and diamonds
            net_mg = books_metal.item_weights({**line, "tunch": None, "fine": None}, fine_optional=True)["net_mg"] or 0
            parts = books_service.half_up(net_mg * books_service.to_paise(line["labour_rate"], "Labour rate"), 1000) \
                + books_service.to_paise(line["diamond_value"], "Diamond value")
            if parts > amount_paise:
                raise EditError(f"Not saved: the amount {amount_paise / 100:,.2f} is less than the labour and diamonds "
                                f"({parts / 100:,.2f}). Ask which figure is right.")
            line.update(settle="Rs", metal_value=f"{(amount_paise - parts) / 100:.2f}")
        with _BOOKS_LOCK:  # one at a time, and a repeated call in this answer gets the first one's reply
            if key in self._book_replies:
                return self._book_replies[key]
            self.emit({"type": "step", "text": f"Saving the {'sale' if sales else 'purchase'} bill for {party}…"})
            company = books_service.get_company(self.bill_company_id)
            with engine.begin() as conn:
                # The same bill saved by two requests at once (two devices, two backend processes: _BOOKS_LOCK holds only
                # within one) takes turns here, so the second finds the first's voucher instead of saving it again.
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                             {"key": f"chat-bill:{self.bill_company_id}:{source}"})
                found = conn.execute(select(books_vouchers.c.id, books_vouchers.c.number).where(
                    books_vouchers.c.company_id == self.bill_company_id, books_vouchers.c.source == source,
                    books_vouchers.c.cancelled.is_(False))).first()
                if found is None and (bill_no or "").strip():  # a bill saved from the chat, named by its number ("iska
                    # price 120000 tha" after INV/26-27/0003 was saved): that bill gets what was given now
                    found = conn.execute(select(books_vouchers.c.id, books_vouchers.c.number).where(
                        books_vouchers.c.company_id == self.bill_company_id, books_vouchers.c.vtype == vtype,
                        books_vouchers.c.number == bill_no.strip(), books_vouchers.c.source.startswith("chat:"),
                        books_vouchers.c.cancelled.is_(False))).first()
                fine_known = bool(found) and bool(conn.execute(select(func.sum(books_metal_lines.c.dr_mg + books_metal_lines.c.cr_mg)).where(
                    books_metal_lines.c.voucher_id == found.id)).scalar())
                # Saved earlier without its price (or with another): this price is what the person says it is now.
                billed = int(conn.execute(select(func.coalesce(func.sum(books_voucher_lines.c.dr_paise), 0)).where(
                    books_voucher_lines.c.voucher_id == found.id)).scalar()) if found else 0
                books_moved = None
                if found and (fine_known or not purity_given) and not (priced and billed != amount_paise):
                    vid, outcome = found.id, "already"  # already in the books as asked: nothing saved again
                else:
                    # A bill dated before the books begin moves the start back, in this same transaction.
                    books_moved = books_imports.fit_books_start(conn, company, [day])
                    if books_moved:
                        company = books_service.get_company(self.bill_company_id, conn)
                    party_id = books_service.ensure_ledger(conn, self.bill_company_id, party,
                                                           "Sundry Debtors" if sales else "Sundry Creditors")
                    items_text = None
                    if not weighed:  # an item that is not jewellery: the bill is its amount, with no metal
                        main = books_service.ensure_ledger(conn, self.bill_company_id, "Sales" if sales else "Purchase",
                                                           "Sales Accounts" if sales else "Purchase Accounts")
                        lines, _summary = books_service.gst_invoice_lines(
                            conn, company, vtype, party_id, [{"ledger_id": main, "taxable": amount_paise, "rate": 0}], False)
                        moved = []
                        items_text = (item or "Item") + (f" × {int(pieces)}" if pieces and pieces > 1 else "")
                    elif purity_given:
                        lines, moved, summary = books_metal.jewellery_invoice(conn, company, vtype, party_id, "gold", [line], 0,
                                                                              not priced, None)  # a price is kept to the paisa
                    else:  # no purity: weights, diamonds and tag kept, fine gold left out (not guessed)
                        lines, moved, summary = books_metal.purity_unknown_invoice(conn, company, vtype, party_id, "gold", [line])
                    self.check_cancelled()  # stopped before the commit: nothing is saved
                    # Saved earlier without purity or price and now given it: the same bill is updated (no second bill).
                    vid = books_service.save_voucher(
                        self.bill_company_id, vtype, day, lines, number=found.number if found else (bill_no or "").strip() or None,
                        narration="Added from the chat", source=source, voucher_id=found.id if found else None, conn=conn,
                        metal=moved, items_text=items_text)
                    outcome = "updated" if found else "saved"
            saved = books_service.get_voucher(self.bill_company_id, vid)
            total_paise = max(sum(l["dr_paise"] for l in saved["lines"]), sum(l["cr_paise"] for l in saved["lines"]))
            stock = next((m for m in saved["metal_lines"] if m.get("net_mg") or m.get("gross_mg")), {})
            self.imports.append({"register": register, "dataset_id": 0, "table": "", "filename": "", "sheet": saved.get("number") or "",
                                 "created": 0 if outcome == "already" else 1, "skipped": 1 if outcome == "already" else 0,
                                 "problems": []})
            # The posted figures, so an answer quoting them is checked against the books (result_rows).
            self.bills.append([total_paise / 100, (stock.get("labour_paise") or 0) / 100, (stock.get("dia_paise") or 0) / 100,
                               (stock.get("net_mg") or 0) / 1000, (stock.get("gross_mg") or 0) / 1000,
                               (stock.get("dr_mg") or stock.get("cr_mg") or 0) / 1000, (stock.get("dia_mct") or 0) / 1000])
            note = {
                "saved": "No GST is charged (the app's bill form has none). Tell the person the bill number and total.",
                "updated": "This bill was saved earlier without its purity or price; it now has what the person gave (same bill "
                           "number, nothing saved twice). Say so in one line.",
                "already": "This exact bill is already in the books (same party, item, weights, tag and date), so it was not "
                           "saved again. Say so; if it really is a second, separate bill, ask for its bill number or tag.",
            }[outcome]
            if not purity_given and weighed and outcome != "already":
                note += (" Purity was not given, so the bill has no fine gold weight (its net weight and diamonds are counted "
                         "in stock); say so in one line.")
            if priced and outcome != "already":
                note += f" The bill is for the amount the person gave, {amount_paise / 100:,.2f}."
            if books_moved:
                note += " " + _books_start_note(books_moved)
            reply = self._book_replies[key] = json.dumps({
                "saved": outcome != "already", "outcome": outcome, "register": register, "bill_no": saved.get("number"),
                "date": str(day), "party": party, "item": item, "total_rupees": total_paise / 100, "note": note,
            }, ensure_ascii=False, default=str)
        return reply

    def _chat_bill(self, number: str, vtype: str) -> dict | None:
        """A bill add_bill saved, by its number: its party, date and item as saved, for an update that names only the
        bill and the figure it lacked. None when there is no such bill."""
        if not number or not self.can_add_bill:
            return None
        with engine.connect() as conn:
            vid = conn.execute(select(books_vouchers.c.id).where(
                books_vouchers.c.company_id == self.bill_company_id, books_vouchers.c.vtype == vtype,
                books_vouchers.c.number == number, books_vouchers.c.source.startswith("chat:"),
                books_vouchers.c.cancelled.is_(False))).scalar()
            if vid is None:
                return None
            ledger_ids = {r.ledger_id for r in conn.execute(select(books_voucher_lines.c.ledger_id).where(
                books_voucher_lines.c.voucher_id == vid))} | {r.ledger_id for r in conn.execute(
                select(books_metal_lines.c.ledger_id).where(books_metal_lines.c.voucher_id == vid))}
            party = conn.execute(select(books_ledgers.c.name).where(
                books_ledgers.c.id.in_(ledger_ids), books_ledgers.c.group_name.in_(("Sundry Debtors", "Sundry Creditors")))).scalar()
        from ..accounts import service as books_service

        saved = books_service.get_voucher(self.bill_company_id, vid)
        stock = next((m for m in saved["metal_lines"] if m.get("net_mg") or m.get("gross_mg")), {})
        grams = lambda mg: mg / 1000 if mg else None  # noqa: E731
        return {"party": party or "", "date": str(saved["date"]), "item": stock.get("item") or (saved.get("items_text") or "").split(" × ")[0],
                "gross_g": grams(stock.get("gross_mg")), "net_g": grams(stock.get("net_mg")),
                "diamond_ct": stock["dia_mct"] / 1000 if stock.get("dia_mct") else None,
                "purity_pct": stock["tunch_bp"] / 100 if stock.get("tunch_bp") else None,
                "tag_no": stock.get("tag_no"), "huid": stock.get("huid"), "color": stock.get("colour"), "clarity": stock.get("clarity")}

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

    def detected(self, table: str) -> tuple[str, dict]:
        """(file name, detection) of a shared sheet: what <documents> says it is."""
        sheet = self.sheets[table]
        filename = (get_dataset(sheet["dataset_id"]) or {}).get("filename", "")
        return filename, detect.classify(sheet, filename)

    def register_for(self, table: str, register: str | None) -> str:
        """The register a shared sheet is added to: the one the person said, else its detected one, else sales."""
        if register in BOOKS_REGISTERS:
            return register
        kind = self.detected(table)[1]["kind"]
        return kind if kind in BOOKS_REGISTERS else "sales"

    def missing_details(self, table: str, register: str | None = None) -> dict:
        """How many of the bills adding the shared sheet would post have no date, or no customer or supplier, of their
        own ({"bills", "skipped", "date", "party"}): the add is rehearsed and rolled back, nothing is posted."""
        self.check_cancelled()
        self.added_to_books = True  # the books can change before it is asked again: never remembered
        self.emit({"type": "step", "text": "Checking the file for missing dates and names…"})
        return books_imports.missing_details(self.company_id, self.sheets[table], self.register_for(table, register))

    def add_to_books(self, table: str, register: str | None = None, party: str | None = None, day=None) -> str:
        """Post a shared sheet to the company's books as POST /api/companies/{id}/import/register does; return the
        counts as JSON for the model. The app calls it when the intent check read a request to add the sheet:
        ``register`` is the one the person said, which wins over what the file looks like; None (they said neither)
        takes the sheet's detected register, or sales when it points to neither. A bill with no date is dated ``day``
        (the date the person gave, else today), one with no customer or supplier is under ``party`` (the one the person
        or the file name gave), else a cash party; what was filled in is then written into the uploaded sheet too.
        Raises EditError/AccountsError on failure."""
        from datetime import date as _date

        self.check_cancelled()
        self.added_to_books = True
        if not self.can_add_to_books:
            raise EditError("No company is chosen, so nothing can be added to the books.")
        if table not in self.sheets:
            raise EditError(f"Unknown table {table!r}; use one of {sorted(self.sheets)}.")
        register = register or None
        if register is not None and register not in BOOKS_REGISTERS:
            raise EditError(f"Unknown register {register!r}; use sales or purchases.")
        sheet = self.sheets[table]
        filename, found = self.detected(table)  # what <documents> says about this sheet
        because = "; ".join(found["reasons"]) or "no clear evidence"
        chosen = register is None
        register = self.register_for(table, register)
        # Added as the person said; a file that clearly looks like the other register is mentioned, never asked about.
        looks_other = found["kind"] in BOOKS_REGISTERS and found["kind"] != register and found["confidence"] == "high"
        # Imports take turns, and a repeat of a call waits for the first and gets its reply.
        with _BOOKS_LOCK:
            if (table, register) in self._book_replies:
                return self._book_replies[(table, register)]
            self.emit({"type": "step", "text": f"Adding {filename} ({sheet['sheet_name']}) to the books as {register}…"})
            day, party = day or _date.today(), party or CASH_PARTY[register]
            party = party.title() if party.islower() else party  # "dummy", "khanak jewellers": saved as a name is written
            try:
                # Stopped before the import commits: nothing is posted, as the person expects.
                result = books_imports.import_register(self.company_id, sheet, register, before_commit=self.check_cancelled,
                                                       default_date=day, default_party=party)
            except AccountsError:
                raise
            except Exception as exc:  # a KeyError here is the import's, not a wrong argument: say so to the model
                raise AccountsError(f"The import failed ({type(exc).__name__}: {exc}).") from exc
            filled = result.get("filled") or {}
            written = []
            if result["created"] and (filled.get("date") or filled.get("party")):
                try:  # the bills are in the books either way: a sheet that could not be written is only mentioned
                    written = books_imports.write_details(self.company_id, sheet, register, day if filled.get("date") else None,
                                                          party if filled.get("party") else None)
                except Exception as exc:  # noqa: BLE001
                    written = [f"The uploaded sheet could not be updated with the date and name ({type(exc).__name__}); "
                               "the bills are in the books."]
            problems = list(result["problems"])
            self.imports.append({"register": register, "dataset_id": sheet["dataset_id"], "table": table, "filename": filename,
                                 "sheet": sheet["sheet_name"], "created": result["created"], "skipped": result["skipped"],
                                 "problems": problems})
            if result["created"] or result["skipped"]:  # in the books now: the upload is filed under this register
                cloud.set_register(sheet["dataset_id"], register)
            reply = self._book_replies[(table, register)] = json.dumps({
                "file": filename,
                "sheet": sheet["sheet_name"],
                "register": register,
                **({"register_note": f"The person did not say sales or purchases, so the app chose {register} from the file: "
                                     f"{because}. Begin the reply with one short line saying which register and why."}
                   if chosen else {}),
                **({"looks_like_note": f"Added as {register}, as the person said, though the file looks like a "
                                       f"{found['label'].lower()} ({because}). Mention it in one short line after the "
                                       "counts, not as a question."} if looks_other else {}),
                **({"books_start_note": _books_start_note(result["books_start"])} if result.get("books_start") else {}),
                "created": result["created"],
                "skipped": result["skipped"],
                "problems": problems[:_PROBLEMS_SHOWN_TO_MODEL],
                "more_problems": max(0, len(problems) - _PROBLEMS_SHOWN_TO_MODEL),
                "notes": [note for note in result["notes"] if not _SHEET_REPORT_NOTE.search(note)] + written,
            }, ensure_ascii=False, default=str)
        self.emit({"type": "step", "text": f"Added {result['created']} entries to the books ({result['skipped']} already there)"})
        return reply

    def result_rows(self) -> list[list]:
        """Every value the tools returned, for answer verification."""
        # Earlier answers are not evidence: rows read from past_chats never confirm a figure.
        rows = [row for q in self.queries if "past_chats" not in str(q.get("sql", "")).lower() for row in q.get("rows", [])]
        rows += [[c["result"]] for c in self.calculations if c["result"] is not None]
        rows += [list(b) for b in self.bills]
        for a in self.analyses:
            if not a.get("error") and (a.get("spec") or {}).get("table") != "past_chats":
                rows += [list(r.values()) for r in a["rows"]]
                rows += [list((a["total"] or {}).values()), [a["rows_matched"], a["groups"]]]
        for check in self.formula_checks:
            if not check.get("error"):
                rows.append([check["rows_checked"], check["rows_blank"], check["matches"], check["mismatches"],
                             check["max_difference"], check["tolerance"]])
                rows += [[e["actual"], e["expected"], e["difference"], e["row"]] for e in check["examples"]]
        for entry in self.imports:
            # Only the counts the model was given: the row numbers inside the problems (row 35...) would confirm any
            # invented count in their range, and the problems it was not shown are no evidence.
            shown = min(len(entry["problems"]), _PROBLEMS_SHOWN_TO_MODEL)
            rows.append([entry["created"], entry["skipped"], len(entry["problems"]), shown, len(entry["problems"]) - shown])
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
