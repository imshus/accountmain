"""What the person's latest message asks the app to do with the books, read by the model in any language: add the files
shared in the chat, or a bill typed in the message, to sales or purchases, with any date and customer / supplier the
person gives for the bills that lack them. The app then adds it (asked for on 2026-10-28: "use the LLM to detect the
person's intention, like 'add this item to sales or purchases'"), asking only for a missing date or name (2026-11-03).

One quick model call without tools, like the follow-up suggestions. When it fails, None: the chat adds nothing and says
so, rather than guess."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date

from .. import config
from . import gpt

TIMEOUT_SECONDS = 15
MAX_OUTPUT_TOKENS = 2000  # room for the reasoning before the short JSON
_MESSAGE_CHARS = 3000
_ANSWER_CHARS = 1500
_PARTY_CHARS = 120
_REGISTERS = ["sales", "purchases", None]

PROMPT = """You read one message a person sent in Accounts.ai, an accounting app for an Indian jewellery business, and say whether it asks the app to add something to their books, and to which register. They write in any language or script (Hinglish, Hindi, English, Gujarati, Marathi, Punjabi, Bengali, Tamil, Telugu...), often short and with typos. Judge the meaning, not particular words.

- add: true when the message asks to add, save, put, post, enter, record or update something in the books, in sales or in purchases ("isko sales me add kr do", "ye purchase me daal do", "add this to sales", "sales me entry kar do", "इसे सेल्स में जोड़ दो", "આને ખરીદીમાં ઉમેરો", "ise kharid me chadha do", "haan add kar do"); or says what a shared file is ("yeh sales data hai", "this is my purchase register", "X.xlsx (Sheet) is purchase data"); or gives a bill's details and says it was sold or bought ("Hukum Chand se gold chain 10g 22k kharida", "Ramesh ko ring 5g 18k becha, labour 500"). false for a question or a request for figures or analysis ("sales ka total kitna hai?", "kya yeh sales data hai?", "month-wise sales dikhao", "is file me kya hai"), for a file shared with no instruction to add it, and for anything else.
- what: "files" when files listed in <files> are to be added; "bill" when the message itself has a bill's details (a party, an item, a weight) to save; null when add is false.
- register: "sales" or "purchases" as the person said or clearly meant for everything in the message: sale, sold, bikri, becha, diya to a customer: sales; purchase, bought, kharid, kharida, liya from a supplier: purchases. null when the message says neither, or has some sales and some purchases (then each file's own register says which).
- files: for "files", one entry per sheet to add. "isko", "ise", "this", "ye", "it" is every sheet marked "latest" (the file shared last); "sab", "all", "dono", "both" is every sheet listed; a file named by its name or kind is its sheets. Each entry: table; register for that file as the person said ("A sales hai, B purchase": each its own), else null; party: the customer or supplier of that file when the message names one ("isko Amit ji ke naam sales me daal do", "supplier Shudhanshu hai", "take supplier as Shudhanshu"), or else when the file's name is a person's or firm's name ("AMIT JI SALE 6 ITEM.xlsx": "Amit Ji"; "HUKKAM CHAND PACKING.xlsx": "Hukkam Chand"; "SURESH JI PRICE LIST.xlsx": "Suresh Ji"; "Garg Jewellers1 (2).xlsx": "Garg Jewellers", without a copy's number), written as a name; null otherwise (the file's own party column is used, or a cash party); party_from: "message" when the person named that party, "file_name" when it comes from the file's name, null when party is null. Empty when what is not "files".
- date: for "files", the date the person gives for the bills, as YYYY-MM-DD: "aaj ki date", "today", "current date" is <today>; "kal" is the day before; "28/10/2026", "28 Oct" (this year) as written, day first. null when they give none.
- anyway: true when the person says to add even though details are missing, without giving them ("aise hi add kro", "jaisa hai waisa daal do", "add anyhow", "koi data na ho to bhi add kr do", "dummy daal do", "cash me daal do", "skip kro"); false otherwise.
- When <earlier answer> is given, the message replies to it: "haan", "yes", "sales", "purchase wala" after an offer to add a file is a request to add that file. After an answer that asked for a missing date or customer / supplier name to add files, a reply giving them ("28/10/2026, supplier Shudhanshu", "aaj ki date aur party Ramesh", "Khanak Jewellers") or saying to go on without them ("aise hi") is add: true, what: "files", for the files that answer named, in the register it named."""


def _schema(tables: list[str]) -> dict:
    """The answer's JSON schema; a file entry may name only a shared sheet's table."""
    table = {"type": "string", "enum": tables} if tables else {"type": "string"}
    entry = {
        "type": "object",
        "properties": {"table": table, "register": {"type": ["string", "null"], "enum": _REGISTERS},
                       "party": {"type": ["string", "null"]},
                       "party_from": {"type": ["string", "null"], "enum": ["message", "file_name", None]}},
        "required": ["table", "register", "party", "party_from"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "add": {"type": "boolean"},
            "what": {"type": ["string", "null"], "enum": ["files", "bill", None]},
            "register": {"type": ["string", "null"], "enum": _REGISTERS},
            "files": {"type": "array", "items": entry},
            "date": {"type": ["string", "null"]},
            "anyway": {"type": "boolean"},
        },
        "required": ["add", "what", "register", "files", "date", "anyway"],
        "additionalProperties": False,
    }


@dataclass
class FileIntent:
    table: str
    register: str | None = None  # the register the person gave this file; None: the message's, else the file's own
    party: str | None = None  # the customer or supplier for bills without one (the message's or the file name's)
    party_given: bool = False  # the person named it (not only the file's name)


@dataclass
class Intent:
    add: bool = False
    what: str | None = None  # "files" or "bill"
    register: str | None = None  # "sales", "purchases", or None: not said, or both kinds in one message
    files: list[FileIntent] = field(default_factory=list)
    day: date | None = None  # the date the person gave for the files' bills
    anyway: bool = False  # add without the missing details, as the person said


def _input(latest: str, previous: str, files: list[dict]) -> str:
    newest = max((f["dataset_id"] for f in files), default=None)
    listed = "\n".join(f'- table {f["table"]}: file "{f["filename"]}", sheet "{f["sheet"]}"'
                       + (" (latest)" if f["dataset_id"] == newest else "") for f in files) or "(no files shared)"
    parts = [f"<today>{date.today().isoformat()}</today>", f"<files>\n{listed}\n</files>"]
    if previous.strip():
        parts.append(f"<earlier answer>\n{previous.strip()[-_ANSWER_CHARS:]}\n</earlier answer>")
    parts.append(f"<message>\n{latest.strip()[:_MESSAGE_CHARS]}\n</message>")
    return "\n\n".join(parts)


def _openai(conversation: str, tables: list[str]) -> dict:
    client = gpt._client().with_options(timeout=TIMEOUT_SECONDS, max_retries=1)  # the same warm connection
    options = {"service_tier": config.OPENAI_SERVICE_TIER} if config.OPENAI_SERVICE_TIER else {}
    response = client.responses.create(
        model=config.OPENAI_MODEL,
        instructions=PROMPT,
        input=[{"role": "user", "content": conversation}],
        reasoning={"effort": config.OPENAI_FOLLOWUP_EFFORT},
        max_output_tokens=MAX_OUTPUT_TOKENS,
        text={"format": {"type": "json_schema", "name": "books_intent", "schema": _schema(tables), "strict": True}},
        **options,
    )
    return json.loads(response.output_text)


def _register(value) -> str | None:
    return value if value in ("sales", "purchases") else None


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def detect(latest: str, previous: str, files: list[dict]) -> Intent | None:
    """The intent of ``latest`` (the person's message; ``previous``: the answer it replies to, without its <context>
    block). ``files``: the shared sheets in the order they were shared ({"table", "dataset_id", "filename", "sheet"}).
    None when the model could not be asked."""
    tables = [f["table"] for f in files]
    try:
        raw = _openai(_input(latest, previous, files), tables)
    except Exception as exc:  # noqa: BLE001 - the answer still comes; it then says nothing was added
        status = getattr(exc, "status_code", None)
        logging.getLogger("uvicorn.error").warning("Books intent not read: %s%s", type(exc).__name__,
                                                   f" ({status})" if status else "")
        return None
    if not raw.get("add"):
        return Intent()
    found = Intent(add=True, what=raw.get("what"), register=_register(raw.get("register")), day=_day(raw.get("date")),
                   anyway=bool(raw.get("anyway")))
    seen = set()
    for entry in raw.get("files") or []:
        if entry.get("table") in tables and entry["table"] not in seen:
            seen.add(entry["table"])
            party = " ".join(str(entry.get("party") or "").split())[:_PARTY_CHARS] or None
            found.files.append(FileIntent(entry["table"], _register(entry.get("register")), party,
                                          bool(party) and entry.get("party_from") == "message"))
    if found.what == "files" and not found.files and files:
        newest = max(f["dataset_id"] for f in files)  # "add it" with nothing named: every sheet of the file shared last
        found.files = [FileIntent(f["table"]) for f in files if f["dataset_id"] == newest]
    return found
