"""Questions the person may ask next, shown as chips under an answer: one quick model call without tools.

The chips are optional, so a missing key, a timeout or a model error gives an empty list instead of an error.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from collections import OrderedDict

from .. import config
from ..database import quote_ident, run_select
from ..duck import sheet_key
from . import PROVIDERS, default_provider, gpt
from .common import _Memo, reply_language, strip_context

MAX_SUGGESTIONS = 3
MAX_CHARS = 90  # longer suggestions are dropped (the prompt asks for under 60)
TIMEOUT_SECONDS = 12
MAX_OUTPUT_TOKENS = 3000  # room for the reasoning before the short answer
_TABLES_CHARS = 3000
_TURNS_SHOWN = 6
_MESSAGE_CHARS = 1200  # each earlier message
_ANSWER_CHARS = 2500  # the latest answer, before its <context> block
_BLOCK_CHARS = 2000  # the latest answer's <context> block
_VALUE_CHARS = 40
_DATES_LISTED = 31  # a date column lists its dates when it has at most this many, else its months
# (most common values, dates or months) listed per column, fewer each time a table is over its share
_LIST_SIZES = ((5, _DATES_LISTED), (2, _DATES_LISTED), (2, 12), (0, 12), (0, 0))

PROMPT = """You suggest follow-up questions in Accounts.ai, an accounting app where a person chats with an AI analyst about the spreadsheets described in <tables>. Read the conversation and write the 3 questions this person is most likely to ask next that the tables can answer.
- Short: at most 8 words (under 60 characters), written the way the person would type them.
- Concrete: name the exact party, item, column or month as written in <tables> or the conversation.
- Varied: for example another party or item, a breakdown (month-wise, party-wise), a comparison, another period.
- New: never a question already asked, and never what the latest answer already shows.
- No amounts or other figures from the answers: name a party, item, column, month or period instead. Write a number only when the person wrote it or <tables> lists it.
- Only dates and periods that exist in the data: <tables> lists the dates (or the months) of each date column.
- The same language and script as the person's latest question: Hinglish stays Hinglish in Latin script, Hindi in Devanagari stays Devanagari, English stays English.
- An answer may end with a <context> block listing the tool calls behind it (table, filters, period): build on it.

<tables>
{tables}
</tables>"""

NO_TABLES = "No files are shared: suggest general accounting questions that follow from the conversation."
JSON_ONLY = '\n\nReply with only this JSON: {"suggestions": ["...", "...", "..."]}'

SCHEMA = {
    "type": "object",
    "properties": {"suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_SUGGESTIONS}},
    "required": ["suggestions"],
    "additionalProperties": False,
}

_ROLES = {"date": "main date", "amount": "main amount", "debit": "debit", "credit": "credit", "category": "main grouping"}
_REGISTERS = {"sales": "; sales register", "purchases": "; purchase register"}
_REGISTERS_TABLE = ("Table registers: the sales and purchase registers together (register, date, party, item, taxable, "
                    "gst, invoice_value).")
_BULLET = re.compile(r"^(?:[-*•·–]+|\(?\d{1,2}[.):])\s+")  # "- ", "• ", "1. ", "2) ", "(3) "
_QUOTE_PAIRS = {'"': '"', "'": "'", "`": "`", "“": "”", "‘": "’", "«": "»"}
# A number as written (5,000; 10.5; 1st; 2025-04-30 is three), not digits in a code (GSTR-3B, 26AS, Q1, ds1_sheet1).
_NUMBER = re.compile(r"(?<!\w)(\d+(?:[.,]\d+)*)(?:st|nd|rd|th)?(?!\w)")

# Suggestions for the same conversation on the same data, so reopening a chat does not ask the model again.
_CACHE: OrderedDict[tuple, list[str]] = OrderedDict()
_CACHE_MAX = 200
_CACHE_LOCK = threading.Lock()
# The distinct dates and months of each date column, read once per version of the sheet.
_DATES = _Memo(64)


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _dates(sheet: dict, column: str) -> tuple[list[str], list[str]]:
    """The distinct dates (YYYY-MM-DD) and months (YYYY-MM) of a date column; either list is empty when it would be
    longer than _DATES_LISTED."""
    def read() -> tuple[list[str], list[str]]:
        table, col = sheet["table_name"], quote_ident(column)
        lists = []
        for width in (10, 7):  # dates are stored as ISO text
            result = run_select(f"SELECT DISTINCT substr({col}, 1, {width}) FROM {quote_ident(table)} "
                                f"WHERE {col} IS NOT NULL ORDER BY 1", {table}, limit=_DATES_LISTED)
            lists.append([] if result.truncated else [row[0] for row in result.rows])
        return lists[0], lists[1]

    return _DATES.get((*sheet_key(sheet), column), read)


def _column(col: dict, roles: dict[str, str], dates: tuple[list[str], list[str]], sizes: tuple[int, int]) -> str:
    """One compact line: name, header in the file, kind, role, and the dates, months or date range, or the most
    common values; ``sizes`` caps how many values and how many dates or months are listed."""
    head = col["name"] + (f' "{col["label"]}"' if col["label"] != col["name"] else "")
    parts = [col["kind"]] + ([roles[col["name"]]] if col["name"] in roles else [])
    stats = col.get("stats") or {}
    top, most_dates = sizes
    if col.get("role") == "identifier":
        parts.append("reference number")
    elif col["kind"] == "date" and "min" in stats:
        listed = next((values for values in dates if 0 < len(values) <= most_dates), None)
        if listed:
            parts.append(("dates " if len(listed[0]) == 10 else "months ") + ", ".join(listed))
        else:
            parts.append(f'{stats["min"]} to {stats["max"]}')
    elif col["kind"] == "text" and stats.get("top") and col["unique"] < col["non_null"] and top:  # not one value per row
        values = ", ".join(repr(_cut(t["value"], _VALUE_CHARS)) for t in stats["top"][:top])
        parts.append(f'{col["unique"]} distinct, most common {values}')
    elif col["kind"] == "text":
        parts.append(f'{col["unique"]} distinct')
    return f"  {head}: {', '.join(parts)}"


def _describe(sheets: list[dict], extra: dict | None, context: str = "") -> str:
    """Table names, columns with their roles, dates and a few exact values: enough to suggest concrete questions,
    in about _TABLES_CHARS characters. Tables named in ``context`` (the latest <context> block) come first; each
    table gets an equal share, and lists fewer values before it loses lines."""
    registers = _REGISTERS_TABLE if extra and "registers" in extra else ""
    budget = (_TABLES_CHARS - len(registers)) // max(1, len(sheets))
    blocks = []
    for sheet in sorted(sheets, key=lambda s: not re.search(rf"\b{re.escape(s['table_name'])}\b", context)):
        profile = sheet["profile"]
        detected = profile.get("summary", {}).get("detected", {})
        roles = {col: _ROLES[role] for role, col in detected.items() if role in _ROLES and col}
        roles.update({col: "tax" for col in detected.get("tax", [])})
        columns = [col for col in profile["columns"] if col["non_null"]]
        dates = {col["name"]: _dates(sheet, col["name"]) for col in columns if col["kind"] == "date"}
        title = (f'Table {sheet["table_name"]} (sheet "{sheet["sheet_name"]}", {sheet["row_count"]} rows'
                 f'{_REGISTERS.get(sheet.get("register"), "")})')
        for sizes in _LIST_SIZES:
            lines = [title] + [_column(col, roles, dates.get(col["name"], ([], [])), sizes) for col in columns]
            if len("\n".join(lines)) < budget:
                break
        blocks.append(_fit(lines, max(budget, len(title) + 1)))  # the table's name at least
    if registers:
        blocks.append(registers)
    return "\n".join(blocks) if blocks else NO_TABLES


def _fit(lines: list[str], limit: int, more: str = "  …") -> str:
    """Whole lines up to ``limit`` characters, then ``more``."""
    kept, size = [], 0
    for line in lines:
        if size + len(line) + 1 > limit:
            kept.append(more)
            break
        kept.append(line)
        size += len(line) + 1
    return "\n".join(kept)


def _latest_context(messages: list[dict]) -> str:
    """The <context> block at the end of the latest answer, cut to _BLOCK_CHARS (whole lines, then "…"); "" when
    that answer does not end with one."""
    answer = next((m["content"] for m in reversed(messages) if m["role"] == "assistant"), "").rstrip()
    start = answer.rfind("<context>")
    if start < 0 or not answer.endswith("</context>"):
        return ""
    block = answer[start:]
    if len(block) > _BLOCK_CHARS:
        body = block[:-len("</context>")].rstrip().split("\n")
        block = _fit(body, _BLOCK_CHARS - len("\n…\n</context>"), more="…") + "\n</context>"
    return block


def _conversation(messages: list[dict], block: str) -> str:
    """The last few turns. Earlier answers lose their <context> block; the latest answer keeps ``block``, since it
    says exactly which table, filters and period the conversation is about."""
    shown = messages[-_TURNS_SHOWN:]
    latest = max((i for i, m in enumerate(shown) if m["role"] == "assistant"), default=-1)
    parts = []
    earlier = [m["content"] for m in messages[:-_TURNS_SHOWN] if m["role"] == "user"]
    if earlier:
        parts.append("Earlier questions: " + " | ".join(_cut(" ".join(q.split()), 100) for q in earlier[-10:]))
    for i, m in enumerate(shown):
        if m["role"] == "user":
            parts.append(f'Person: {_cut(m["content"], _MESSAGE_CHARS)}')
            continue
        body = strip_context(m["content"])
        if i == latest:
            parts.append(f'Assistant: {_cut(body, _ANSWER_CHARS)}' + (f"\n\n{block}" if block else ""))
        else:
            parts.append(f'Assistant: {_cut(body, _MESSAGE_CHARS)}')
    question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    return "<conversation>\n" + "\n\n".join(parts) + f"\n</conversation>\n\nThe person's latest question: {_cut(question, 300)}"


def _normal(text: str) -> str:
    return " ".join(text.casefold().split()).rstrip("?.!। ")


def _numbers(text: str) -> set[float]:
    found = set()
    for match in _NUMBER.finditer(text):
        number = match.group(1).replace(",", "")
        found.update(float(part) for part in (number.split(".") if number.count(".") > 1 else [number]))
    return found


def clean(raw, asked: list[str], tables: str = "") -> list[str]:
    """At most MAX_SUGGESTIONS tidy questions: no quotes, bullets or numbering, single spaces, nothing over MAX_CHARS,
    no repeats, nothing the person already asked, and no number that neither the person nor ``tables`` (the tables
    description) wrote: an amount copied from an answer, or a date that is not in the data."""
    seen = {_normal(q) for q in asked}
    allowed = _numbers(" ".join([*asked, tables]))
    out = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        for _ in range(2):  # "1. "Garg ka total?"" and ""1. Garg ka total?"" both come out clean
            text = _BULLET.sub("", text).strip()
            # Only one pair around the whole text: "'SATYAM JEWELLERS' vs 'GARG JEWELLERS'" keeps its quotes.
            if len(text) > 1 and _QUOTE_PAIRS.get(text[0]) == text[-1] and not {text[0], text[-1]} & set(text[1:-1]):
                text = text[1:-1].strip()
        key = _normal(text)
        if not key or len(text) > MAX_CHARS or key in seen or not _numbers(text) <= allowed:
            continue
        seen.add(key)
        out.append(text)
        if len(out) == MAX_SUGGESTIONS:
            break
    return out


def _openai(instructions: str, conversation: str) -> list:
    client = gpt._client().with_options(timeout=TIMEOUT_SECONDS, max_retries=0)  # the same warm connection
    options = {"service_tier": config.OPENAI_SERVICE_TIER} if config.OPENAI_SERVICE_TIER else {}
    response = client.responses.create(
        model=config.OPENAI_MODEL,
        instructions=instructions,
        input=[{"role": "user", "content": conversation}],
        reasoning={"effort": config.OPENAI_FOLLOWUP_EFFORT},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        text={"format": {"type": "json_schema", "name": "followups", "schema": SCHEMA, "strict": True}},
        **options,
    )
    return json.loads(response.output_text)["suggestions"]


def _anthropic(instructions: str, conversation: str) -> list:
    import anthropic  # loaded on first use, as in claude.py

    client = anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=0)
    message = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=instructions + JSON_ONLY,
        messages=[{"role": "user", "content": conversation}],
        output_config={"effort": "low"},
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    return json.loads(text[text.find("{"):text.rfind("}") + 1])["suggestions"]


_CALLS = {"openai": _openai, "anthropic": _anthropic}


def suggest(messages: list[dict], sheets: list[dict], extra: dict | None = None,
            provider_id: str | None = None) -> list[str]:
    """Up to MAX_SUGGESTIONS short questions the person may ask next about ``sheets`` (none: general accounting).
    ``messages`` is the conversation as the chat endpoints receive it, ending with the latest answer."""
    provider = PROVIDERS[provider_id or default_provider()]
    if not provider.configured():
        return []
    conversation = hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()
    key = (provider.id, provider.model, tuple(sheet_key(s) for s in sheets), conversation)
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return list(_CACHE[key])
    try:
        block = _latest_context(messages)
        tables = _describe(sheets, extra, block)
        instructions = PROMPT.format(tables=tables)
        language = reply_language(messages)
        if language:  # the person's language, even when the answers drifted into another
            instructions += f"\n\nWrite the suggestions in {language}, the language of the person's latest message."
        raw = _CALLS[provider.id](instructions, _conversation(messages, block))
    except Exception as exc:  # noqa: BLE001 - the chips are optional; the answer above them is unaffected
        status = getattr(exc, "status_code", None)
        logging.getLogger("uvicorn.error").warning(
            "Follow-up suggestions skipped: %s%s", type(exc).__name__, f" ({status})" if status else "")
        return []
    suggestions = clean(raw, [m["content"] for m in messages if m["role"] == "user"], tables)
    with _CACHE_LOCK:
        _CACHE[key] = suggestions
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return list(suggestions)
