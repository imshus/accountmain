"""Pieces every chat model shares: the instructions, the table context and the tools (analyse, SQL, calculate)."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
from collections import OrderedDict
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field

import pandas as pd

from .. import analysis, cloud, detect
from ..accounts import imports as books_imports
from ..accounts.service import AccountsError
from ..calc import CalcError, evaluate_number, format_decimal
from ..database import QueryError, engine, get_dataset, quote_ident, read_preview, run_select
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

Adding to the books:
- Call add_to_books only when the person's latest message says a shared file is sales or purchase data or a register, or asks to add, save or post it to the books, in any language ("yeh sales data hai", "this is my purchase register", "ise sales mein daal do", "isko purchase me add karo", "isko books mein daal do", "add this file"), or answers your question which register it is ("purchase", or "haan" to "Lagta hai yeh purchase register hai - sahi hai?"). Earlier messages never call it. Never for a question, whether about the data ("sales data ka total kitna hai?") or about what a file is ("kya yeh sales data hai?"): answer it, and you may offer to add the file. If it is unclear which file or which register, ask. Without the add_to_books tool (no company chosen in the app, or no file shared), say what is missing.
- The register is the one the person names. If they name none, decide from the file itself: its detection in <documents> (kind, confidence and evidence, such as the file name) and its columns and values in <tables>. A sales or purchase detection with high confidence and no evidence the other way is clear: call add_to_books without a register (the app uses that detection). A medium- or low-confidence, mixed or other detection (bank statement, ledger) is unclear: ask.
- If the person names one register but <documents> detects the other with high confidence, do not add it yet: say in one line what the file looks like and why, and ask whether to add it as the register they named or as the detected one, naming both. Their answer decides.
- After it runs, say in the person's language how many entries were added and how many were already in the books, exactly as it returned them, and mention its problems briefly (what went wrong, and how many problems in all), without row numbers. Never invent counts. If you left the register out, first say in one short line which register you chose and why (e.g. the file name, or a Type column of "S").
- When <documents> lists shared files as "Not in the books yet", the person has not said which register they are: unless this answer adds them, end it with ONE short question in the person's language asking which it is, e.g. "Yeh sales ka data hai ya purchase ka?" (with a likely register listed: "Lagta hai yeh purchase register hai - sahi hai?"); the app shows Sales and Purchase buttons under it. Being listed is never a reason to call add_to_books: only the person's own words are.

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

BOOKS_TOOL_DESCRIPTION = (
    "Add one shared sheet to the chosen company's books as its sales or purchase register (the one the person named, or "
    "the detected one when they named none), exactly as the app's import does: each invoice becomes a voucher. Rows "
    "already in the books are skipped, so calling it again adds nothing twice. Returns how many entries were added, how "
    "many were already there, and any problems."
)
BOOKS_PARAMS = {
    "table": "The shared sheet to add, e.g. ds2_sheet1.",
    "register": "sales for a sales register (invoices to customers), purchases for a purchase register (bills from suppliers), "
                "as the person said; null when they did not say: the app then uses the register detected for the sheet "
                "(see <documents>) and refuses an unclear detection.",
}
BOOKS_REGISTERS = ("sales", "purchases")
_PROBLEMS_SHOWN_TO_MODEL = 10
# A latest message that is a question ("kya yeh sales data hai?", "sales ka total kitna hai") adds nothing to the books,
# unless it also asks to add. A question ends in "?" or has a question word: at the start in English, anywhere in Hindi.
_LETTER = _DEVANAGARI.pattern
_QUESTION = re.compile(
    r"[?？]\s*$|^\W*(?:what|which|who|whose|why|how|when|where|does|did|can|could|would|should|will|shall"
    r"|is\s+(?:this|it|that|the|there|my)|are\s+(?:these|they|there|the|my))\b"
    r"|\b(?:kya|kitn[aei]|kaun(?:sa|si|se)?|kab|kahaa?n|ky(?:on|un|u)|kaise)\b"
    rf"|(?<!{_LETTER})(?:क्या|कितन[ाीे]|कौन(?:सा|सी|से)?|कब|कहा[ँं]|क्यों|क्यूँ?|कैसे)(?!{_LETTER})", re.IGNORECASE)
# Asking to add takes an add verb, whole ("add up", "jod" and "जोड़" alone are a total; "Chadha" is a name), and what
# to add or where: "add this file", "save it to purchases", "post it in the books", "isko sales mein daal do", "ise jod do",
# "इसे सेल्स में डाल दो".
_HI_THEN = r"\s+(?:do|de|dena|dein|dijiye|dijie|diya|du|dun|doon|sakte|sakti|sakta)"
_DEVA_THEN = r"\s*(?:दो|दे|दें|दीजिए|दीजिये|दिया|दूँ|दूं|सकते|सकती|सकता)"
_ADD_VERB = (rf"\b(?:(?:add|save|post|import|entry|enter)\s+kar\w*|daa?l(?:o|na|{_HI_THEN})"
             rf"|(?:jod|chadh?a)(?:na|{_HI_THEN})|chadh?ao)\b"
             rf"|(?<!{_LETTER})(?:(?:ऐड|एड|सेव|पोस्ट|इम्पोर्ट|एंट्री)\s*कर|डाल(?:ो|ना|{_DEVA_THEN})"
             rf"|जो(?:\u095c|\u0921\u093c)(?:ना|{_DEVA_THEN})|च(?:\u095d|\u0922\u093c)ा(?:ओ|ना|{_DEVA_THEN}))")
_ADD_TARGET = (r"\b(?:ise|isko|inhe|inhen|inko|file|sheet|data)\b"
               r"|\b(?:books?|bahi|khat[ae]|registers?|tally|sales?|purchases?|kharid\w*|bikri)\s+(?:mein|me|men|main|par|pe)\b"
               rf"|(?<!{_LETTER})(?:इसे|इसको|इन्हें|इनको|(?:\u092b\u093c?|\u095e)ाइल"
               r"|(?:बही|खात[ाे]|रजिस्टर|सेल्स|परचे(?:\u091c\u093c?|\u095b)|खरीद|बिक्री|बुक्स?)\s*(?:में|पर|पे))")
_ASKS_TO_ADD = re.compile(
    r"\b(?:add|save|post|import)\b(?!(?:\s+\w+){0,2}\s+up\b)(?:"
    r"(?:\s+(?:the|this|that|these|those|my|our|whole|entire|all|of)\b)*\s+(?:(?:files?|sheets?|data|registers?|workbook)\b"
    r"|(?:it|this|these|them)(?=\s*(?:$|[?.!,]|(?:to|in|into|as)\b)))"
    r"|[^.?!]{0,40}?\b(?:to|into|in)\s+(?:the\s+|my\s+|our\s+)?(?:books?|tally|accounts)\b)"
    rf"|(?:{_ADD_TARGET})[^.?!।]{{0,60}}?(?:{_ADD_VERB})|(?:{_ADD_VERB})[^.?!।]{{0,60}}?(?:{_ADD_TARGET})", re.IGNORECASE)


def _word_set(words: str) -> frozenset[str]:
    return frozenset(unicodedata.normalize("NFC", w) for w in words.split())


# Saying which register a file is, in so many words: "this" (or the file's name), "is" / "hai" and the register, in Hindi
# or English word order ("yeh purchase (ka) data hai", "AI SAMPLE.xlsx sales data hai", "This is my purchase register",
# "यह सेल्स डेटा है"); or a short reply to an answer that ended asking which register ("purchase", "sales wala", "haan"
# to "Lagta hai yeh purchase register hai - sahi hai?"). A request that only mentions sales or purchases ("month-wise
# sales dikhao", "Top 10 customers by sales", the app's own "which is the sales register" prompt) says nothing about a file.
_THIS = _word_set("yeh ye yah yahi yehi this that it these those यह ये यही")
_IS = _word_set("hai hain he h is are was were है हैं")
_FILE = _word_set("file sheet excel फ़ाइल फाइल शीट")  # "ye file purchase ki hai", "this file is sales data"
_ARTICLE = _word_set("the my our a an all")  # "this is my purchase register"
_REGISTER_TAIL = _word_set("ka ki ke wala wali wale vala vali data register bahi file sheet bill bills entries invoices "
                           "khata का की के वाला वाली वाले डेटा डाटा रजिस्टर बही फ़ाइल फाइल शीट बिल")
_YES = _word_set("haan han haa ha yes yeah yep ji sahi correct right theek thik ok okay bilkul हाँ हां जी सही")
_NO = _word_set("nahi nahin nhi no not galat wrong नहीं गलत")
_REPLY_WORDS = (_THIS | _IS | _FILE | _ARTICLE | _REGISTER_TAIL | _YES | _NO
                | _word_set("ya or only sirf hi bhi wo woh vo mein me men main par pe में"))  # "purchase", "sales mein"
_DOCUMENT = re.compile(r"\.(?:xlsx|xlsm|xls|csv)$")  # a file name says which file: "oct data.xlsx purchase data hai"


def _words(text: str) -> list[str]:
    """A message's words, lower case: "it's" as "it is", a file name's last word whole, without a "(sheet)" after it."""
    text = re.sub(r"(\.(?:xlsx|xlsm|xls|csv))\s*\([^)]{0,120}\)", r"\1", unicodedata.normalize("NFC", text).lower())
    text = re.sub(r"\b(it|that|this)['’]s\b", r"\1 is", text)
    return [w for w in (w.rstrip(".") for w in re.findall(r"[^\s,;:!?？।()\"'“”‘’]+", text)) if w]


def _register_word(word: str) -> bool:
    return not _DOCUMENT.search(word) and bool(detect.registers_named(word))


def _skip(words: list[str], start: int, allowed: frozenset[str], most: int = 1) -> int:
    end = start
    while end < len(words) and end - start < most and words[end] in allowed:
        end += 1
    return end


def _states_register(words: list[str]) -> bool:
    at = lambda k, test: k < len(words) and test(words[k])  # noqa: E731
    for i, word in enumerate(words):
        if word in _THIS or _DOCUMENT.search(word):
            j = _skip(words, i + 1, _FILE)
            if at(j, _register_word) and at(_skip(words, j + 1, _REGISTER_TAIL, 3), _IS.__contains__):
                return True  # yeh purchase (ka) data hai, AI SAMPLE.xlsx sales data hai, यह सेल्स डेटा है
            if at(j, _IS.__contains__) and at(_skip(words, j + 1, _ARTICLE), _register_word):
                return True  # this is (my) purchase register, it is sales data
        elif _register_word(word):
            k = _skip(words, i + 1, _REGISTER_TAIL, 3)
            if at(k, _IS.__contains__) and at(k + 1, _THIS.__contains__):
                return True  # purchase data hai yeh
    return False


def _asked_register(previous: str) -> set[str]:
    """The registers an answer ended asking about: named in a question in its last line ("Yeh sales ka data hai ya
    purchase ka?"), or both named there as a choice ("Kripya batayein ise sales mein daalun ya purchases mein.")."""
    lines = previous.strip().splitlines()
    last = lines[-1] if lines else ""
    questions = re.findall(r"[^.!?？।]*[?？]", last)
    named = detect.registers_named(last)
    return (detect.registers_named(questions[-1]) if questions else set()) or (named if len(named) == 2 else set())


def says_register(request: str, previous: str = "") -> bool:
    """The person's message says which register a shared file is ("yeh purchase data hai", "isko sales mein daal do", or
    "purchase" / "haan" when ``previous``, the answer it replies to, ended asking), rather than only asking about one
    ("kya yeh sales data hai?") or mentioning one ("month-wise sales dikhao")."""
    if _ASKS_TO_ADD.search(request):
        return bool(detect.registers_named(request))
    if _QUESTION.search(request):
        return False
    words = _words(request)
    if _states_register(words):
        return True
    asked = _asked_register(previous)
    if not asked or not words or len(words) > 8 or not all(w in _REPLY_WORDS or _register_word(w) for w in words):
        return False
    # "haan" / "sahi hai" confirms the one register the question named; "nahi" alone names none.
    return any(_register_word(w) for w in words) or (len(asked) == 1 and any(w in _YES for w in words)
                                                     and not any(w in _NO for w in words))


def pending_text(pending: list[dict]) -> str:
    """For <documents>: the shared sheets whose register the answer asks about (each {filename, sheet, suggestion})."""
    likely = {"sales": "likely the sales register", "purchases": "likely the purchase register"}
    return "\n".join(["Not in the books yet (the chosen company's books have nothing from these sheets, and the person has "
                      "not said which register they are):"]
                     + [f'- File "{p["filename"]}", sheet "{p["sheet"]}": '
                        + likely.get(p["suggestion"], "a sales or purchase register, unclear which") for p in pending])


def books_tool_schema(tables) -> dict:
    """add_to_books' parameters: one of these tables and a register, or null for the detected one."""
    return {
        "type": "object",
        "properties": {
            "table": {"type": "string", "enum": sorted(tables), "description": BOOKS_PARAMS["table"]},
            "register": {"type": ["string", "null"], "enum": [*BOOKS_REGISTERS, None], "description": BOOKS_PARAMS["register"]},
        },
        "required": ["table", "register"],
        "additionalProperties": False,
    }


# Imports take turns: two at once could both find a row not yet posted and post it twice.
_BOOKS_LOCK = threading.Lock()


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
    # The company whose books add_to_books posts the shared sheets to; None: the model has no such tool.
    company_id: int | None = None
    # The person's latest message: only it can ask for add_to_books, and a question there is answered, not imported.
    # "" outside a chat (a direct call), where nobody's words are checked.
    request: str = ""
    # The answer that message replies to ("" when there is none), without its <context> block.
    previous: str = ""
    imports: list[dict] = field(default_factory=list)
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

    def add_to_books(self, table: str, register: str | None = None) -> str:
        """Post a shared sheet to the company's books as POST /api/companies/{id}/import/register does; return the
        counts as JSON for the model. Without ``register`` the sheet's detection decides, only when it is clear (high
        confidence, no evidence for the other register); a register that a high-confidence detection contradicts needs
        the person's answer to the AI's question naming both registers. Raises EditError/AccountsError on failure."""
        self.check_cancelled()
        self.added_to_books = True
        if not self.can_add_to_books:
            raise EditError("No company is chosen, so nothing can be added to the books. Ask the person to choose one in the app.")
        if table not in self.sheets:
            raise EditError(f"Unknown table {table!r}; use one of {sorted(self.sheets)}.")
        register = register or None  # an empty string from the model means left out
        if register is not None and register not in BOOKS_REGISTERS:
            raise EditError(f"Unknown register {register!r}; use sales or purchases.")
        if _QUESTION.search(self.request) and not _ASKS_TO_ADD.search(self.request):
            raise EditError("The person's latest message is a question, not a request to add the file to the books. Answer "
                            "it, and ask whether to add the file before calling add_to_books.")
        # Only the person's own words add a file: saying which register it is, or asking to add it. A message that only
        # mentions sales or purchases (the app's own prompts too), or a file listed as not in the books, is no reason.
        if self.request and not (says_register(self.request, self.previous) or _ASKS_TO_ADD.search(self.request)):
            raise EditError("Not added: the person's latest message neither says which register a shared file is nor asks "
                            "to add it to the books. Answer it; for a file not in the books yet, ask whether it is their "
                            "sales or purchase data, and add it only once they say.")
        sheet = self.sheets[table]
        filename = (get_dataset(sheet["dataset_id"]) or {}).get("filename", "")
        found = detect.classify(sheet, filename)  # what <documents> says about this sheet
        because = "; ".join(found["reasons"]) or "no clear evidence"
        chosen = register is None
        if chosen:
            if found["kind"] not in BOOKS_REGISTERS or found["confidence"] != "high" or found["against_register"]:
                against = "; ".join(found["against_register"])
                raise EditError(f"Not added: the person did not say which register, and the detection is unclear "
                                f"({found['label']}, {found['confidence']} confidence; {because}"
                                + (f"; evidence the other way: {against}" if against else "")
                                + "). Ask whether it is their sales or purchase register.")
            register = found["kind"]
        # The answer the person replies to raised the conflict only if it named both registers, as this refusal asks.
        elif (found["kind"] in BOOKS_REGISTERS and found["kind"] != register and found["confidence"] == "high"
              and not {register, found["kind"]} <= detect.registers_named(self.previous)):
            raise EditError(f"Not added: the person said {register}, but the file looks like a {found['label'].lower()} "
                            f"(high confidence; {because}). Say in one line what it looks like and why, and ask whether to "
                            f"add it as {register} or as {found['kind']}, naming both; add it as {register} only when they "
                            "confirm.")
        # Imports take turns, and a repeat of a call waits for the first and gets its reply.
        with _BOOKS_LOCK:
            if (table, register) in self._book_replies:
                return self._book_replies[(table, register)]
            self.emit({"type": "step", "text": f"Adding {filename} ({sheet['sheet_name']}) to the books as {register}…"})
            try:
                # Stopped before the import commits: nothing is posted, as the person expects.
                result = books_imports.import_register(self.company_id, sheet, register, before_commit=self.check_cancelled)
            except AccountsError:
                raise
            except Exception as exc:  # a KeyError here is the import's, not a wrong argument: say so to the model
                raise AccountsError(f"The import failed ({type(exc).__name__}: {exc}).") from exc
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
                **({"register_note": f"You left the register out, so the app chose {register} from the detection: {because}. "
                                     "Begin the reply with one short line saying which register you chose and why."}
                   if chosen else {}),
                "created": result["created"],
                "skipped": result["skipped"],
                "problems": problems[:_PROBLEMS_SHOWN_TO_MODEL],
                "more_problems": max(0, len(problems) - _PROBLEMS_SHOWN_TO_MODEL),
                "notes": result["notes"],
            }, ensure_ascii=False, default=str)
        self.emit({"type": "step", "text": f"Added {result['created']} entries to the books ({result['skipped']} already there)"})
        return reply

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
