"""Chat about an upload with GPT-6 Luna.

Both models get the same instructions and the same tools: ``analyse`` (totals and
breakdowns on exact decimals, no SQL), ``run_sql`` (read-only DuckDB, limited to the tables
of the selected upload), ``calculate`` (exact decimal arithmetic) and ``check_formula``. Whether the person asks to add a
shared file or a typed bill to sales or purchases is read first by a short model call (intent.py), in any language: the
app then adds the files itself before the answer, or gives the model ``add_bill`` for the typed bill; nothing is asked.
After each answer every figure in it is checked against what the tools
returned; if any figure does not match, the model is asked once to recompute and
correct its answer, and whatever is still unverified is reported to the user.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as _date

from .. import config
from ..duck import sheet_key
from . import gpt, intent
from .books_data import unreadable_note
from .common import (BOOKS_REGISTERS, EMPTY_ANSWER, REPAIR_PROMPT, CancelEvent, Cancelled, LLMError, Reply, Toolbox,
                     build_instructions, is_fallback, pending_text, repeated_sheets, reply_language, strip_context,
                     summary_sheets, tool_error)
from .verify import indian_digits, known_values, verify

__all__ = ["CancelEvent", "Cancelled", "LLMError", "chat", "default_provider", "provider_status", "strip_context"]

_MODEL_LABELS = {
    "gpt-6-luna": "GPT-6 Luna",
    "gpt-6-sol": "GPT-6 Sol",
}


@dataclass(frozen=True)
class Provider:
    id: str
    model: str
    key_name: str
    configured: Callable[[], bool]
    # (messages, instructions, tools, emit, effort[, transcript=]) -> Reply (or (answer, model))
    run: Callable[..., Reply | tuple[str, str]]
    effort: Callable[[], str]
    repair_effort: Callable[[], str]
    streams: bool  # passes answer text on as it is written

    @property
    def label(self) -> str:
        return _MODEL_LABELS.get(self.model, self.model)


PROVIDERS = {
    "openai": Provider("openai", config.OPENAI_MODEL, "OPENAI_API_KEY", config.openai_configured, gpt.chat,
                       lambda: config.OPENAI_REASONING_EFFORT, lambda: config.OPENAI_REPAIR_EFFORT, True),
}

# Answers to the same conversation on the same data, so asking again is instant. Only checked, complete
# answers are kept (never a refusal, a cut-off answer, a stopped one or one that added to the books), and any change
# to a sheet changes the key.
_ANSWERS: OrderedDict[tuple, dict] = OrderedDict()
_ANSWERS_MAX = 200
_ANSWERS_LOCK = threading.Lock()


def _answer_key(provider: Provider, messages: list[dict], sheets: list[dict], extra: dict | None,
                documents: str | None, combined: bool, company_id: int | None = None,
                pending: list[dict] | None = None) -> tuple:
    extra_keys = tuple(sorted((name, str(frame.attrs.get("cache_key"))) for name, (frame, *_rest) in (extra or {}).items()))
    # A chat about shared files (told what each file is) must not reuse an answer given without that context.
    # The comparison text is derived from the registers in ``extra``, which the key already covers. The company
    # decides whether the model may add to the books, and whose: an answer for another company is never reused. An
    # answer asking which register a file is holds only while the file is still not in the books, and the reverse.
    # "Today" changes at midnight, so does every answer that used it.
    return (provider.id, provider.model, provider.effort(), tuple(sheet_key(s) for s in sheets), extra_keys, documents,
            combined, company_id, json.dumps(pending or [], sort_keys=True), json.dumps(messages, ensure_ascii=False),
            _date.today().isoformat())


def default_provider() -> str:
    """The chat model: GPT (OpenAI) is the only one."""
    return "openai"


_ADDED = ("<added>\nThe app added these shared files to the books just now, because the person's latest message asked "
          "for it, so \"this\", \"it\" or \"isko\" there means these files. Begin the reply with each one, by its file name; "
          "a bill typed in an earlier message is not part of this request, so do not report it again (one result per "
          "file, as JSON):\n{results}\n</added>")
_NOTHING_SHARED = ("<added>\nThe person asked to add a file to the books, but no file is shared in this chat: say so in one "
                   "line, and that they can attach it with the + button.\n</added>")
# A file whose bills lack a date or a customer / supplier is added only once the person gives them, or says to go on
# without (asked for on 2026-11-03: "user se proper input lo"; "sare me wo apply kr do").
_NEEDS = ("<needs>\nThe person asked to add these files, but some of their bills have no date, or no customer / supplier, in "
          "the file, so they were NOT added yet. In the person's language, ask in ONE short question for exactly what is "
          "missing, naming each file and the register it goes to: the date of the bills, and the customer (sales) or "
          "supplier (purchases), suggesting the name from the file's name when given. Say they can reply with them, or "
          "with \"aise hi add kro\" to add with today's date and the suggested name (else Cash Customer / Cash Supplier), "
          "and that what they give is written into the sheet as well. Never say these files were added (one per file, as "
          "JSON):\n{asks}\n</needs>")


def _add_files(tools: Toolbox, wanted: intent.Intent) -> tuple[str, set[str]]:
    """Add the shared sheets the person asked for (read by the intent check) to the books, each in the register they
    said for it (else the message's, else the sheet's own), with the date and customer or supplier they gave on the
    bills that have none (else today and the file name's party or a cash one, when they said to go on without). A
    sheet whose bills lack a date or party the person did not give is not added: the answer asks for them (<needs>).
    A sheet that only repeats another one's items is left out. Returns the <added> / <needs> blocks the answer
    reports, and the tables it dealt with (no Sales / Purchase buttons for them). A file that fails is reported
    there, the others are still added."""
    if not tools.sheets:
        return _NOTHING_SHARED, set()
    sheets = [tools.sheets[f.table] for f in wanted.files]

    def said(f: intent.FileIntent) -> str | None:
        """The register the person gave this sheet: its own; else the message's, except for a sheet of a file of
        several that clearly is the other register (a Purchase sheet in a workbook added "to sales")."""
        if f.register:
            return f.register
        upload = tools.sheets[f.table]["dataset_id"]
        if wanted.register and sum(s["dataset_id"] == upload for s in sheets) > 1:
            found = tools.detected(f.table)[1]
            if found["kind"] in BOOKS_REGISTERS and found["kind"] != wanted.register and found["confidence"] == "high":
                return found["kind"]
        return wanted.register

    registers = {f.table: tools.register_for(f.table, said(f)) for f in wanted.files}
    summaries = summary_sheets(sheets, registers)
    repeated = repeated_sheets([s for s in sheets if s["table_name"] not in summaries], registers)
    results, asks = [], []
    for f in wanted.files:
        if f.table in summaries:
            bills = tools.sheets[summaries[f.table]]
            results.append(json.dumps({"table": f.table, "sheet": tools.sheets[f.table]["sheet_name"], "not_added":
                                       f"It only totals the bills in sheet {bills['sheet_name']!r} of the same file (its "
                                       "totals equal theirs), which were added instead, so nothing is counted twice. "
                                       "Mention it in one short line."}, ensure_ascii=False))
            continue
        if f.table in repeated:
            twin = tools.sheets[repeated[f.table]]
            results.append(json.dumps({"table": f.table, "sheet": tools.sheets[f.table]["sheet_name"], "not_added":
                                       f"Every item or bill in it is also in sheet {twin['sheet_name']!r} of the same file, "
                                       "which was added instead, so nothing is counted twice. Mention it in one short line."},
                                      ensure_ascii=False))
            continue
        try:
            if not wanted.anyway and (wanted.day is None or not f.party_given):
                gaps = tools.missing_details(f.table, said(f))
                no_date, no_party = (gaps["date"] if wanted.day is None else 0), (0 if f.party_given else gaps["party"])
                if no_date or no_party:
                    sheet = tools.sheets[f.table]
                    asks.append(json.dumps({
                        "file": tools.detected(f.table)[0], "sheet": sheet["sheet_name"], "register": tools.register_for(f.table, said(f)),
                        "bills": gaps["bills"], "bills_with_no_date": no_date, "bills_with_no_customer_or_supplier": no_party,
                        "name_from_file_name": None if f.party_given else f.party}, ensure_ascii=False))
                    continue
            results.append(tools.add_to_books(f.table, said(f), f.party, wanted.day))
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - reported in the answer, as a tool's error would be
            results.append(json.dumps({"table": f.table, "error": tool_error(exc)}, ensure_ascii=False))
    blocks = ([_ADDED.format(results="\n".join(results))] if results else []) + ([_NEEDS.format(asks="\n".join(asks))] if asks else [])
    return "\n\n".join(blocks), {f.table for f in wanted.files}


def provider_status() -> list[dict]:
    return [
        {"id": p.id, "label": p.label, "model": p.model, "configured": p.configured(), "key_name": p.key_name}
        for p in PROVIDERS.values()
    ]


def chat(provider_id: str | None, messages: list[dict], sheets: list[dict], extra: dict | None = None, emit=None,
         fresh: bool = False, documents: str | None = None, combined: Callable[[], str] | None = None,
         cancel: threading.Event | None = None, company_id: int | None = None, pending: list[dict] | None = None,
         bill_company_id: int | None = None, files: list[dict] | None = None) -> dict:
    """Answer the conversation. ``emit`` receives live progress: steps, answer text as it is written,
    and "reset" when a draft is replaced (a correction round). ``combined`` returns the registers comparison
    added to ``documents``; it is called only when the answer is not remembered (it can take seconds).
    With ``company_id`` (an existing company) and sheets, a sheet the person asks to add goes into that company's books.
    ``pending``: shared sheets not in that company's books; the answer offers to add them, and returns them as
    pending_registers unless it added a sheet to the books.
    ``bill_company_id``: the company a typed bill the person asks to save goes to (add_bill), with or without files.
    ``files``: what each shared sheet is ({"table_name", "filename", ...}, from main._shared_files), for the intent check.
    Once ``cancel`` is set the answer stops with Cancelled and is not kept."""
    send = emit or (lambda _event: None)

    def emit(event: dict) -> None:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        send(event)

    provider = PROVIDERS[provider_id or default_provider()]
    if not provider.configured():
        raise LLMError(
            503, f"{provider.label} is not set up. Add {provider.key_name} to backend/.env and restart the backend."
        )
    company_id = company_id if sheets else None
    pending = list(pending or []) if company_id is not None else []
    key = _answer_key(provider, messages, sheets, extra, documents, combined is not None, company_id, pending)
    with _ANSWERS_LOCK:
        remembered = copy.deepcopy(_ANSWERS[key]) if key in _ANSWERS and not fresh else None
        if remembered:
            _ANSWERS.move_to_end(key)
    if remembered:
        emit({"type": "delta", "text": remembered["answer"]})
        return {**remembered, "cached": True}

    latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    # The answer the latest message replies to ("haan, sales" after an offer to add a file).
    previous = messages[-2]["content"] if len(messages) > 1 and messages[-2]["role"] == "assistant" else ""
    # Whether the person asks to add a shared file or a typed bill to sales or purchases: read by the model, in any
    # language. Only something that could be added is checked: shared files, or a message with a number (a bill's weight).
    checked = (company_id is not None or bill_company_id is not None) and bool(sheets or any(c.isdigit() for c in latest))
    wanted = None
    if checked:
        emit({"type": "step", "text": "Reading what you asked…"})
        names = {f["table_name"]: f for f in files or []}
        # In the order shared (each file's sheets in the workbook's order), so "the latest file" is the one shared last.
        shared = [{"table": s["table_name"], "dataset_id": s["dataset_id"], "sheet": s["sheet_name"],
                   "filename": names.get(s["table_name"], {}).get("filename", "")} for s in sheets]
        wanted = intent.detect(latest, strip_context(previous), shared)
    add_files = bool(wanted and wanted.add and wanted.what == "files")
    add_bill = bool(wanted and wanted.add and wanted.what == "bill" and bill_company_id is not None)
    tools = Toolbox({sheet["table_name"]: sheet for sheet in sheets}, extra, emit=emit, cancel=cancel, company_id=company_id,
                    bill_company_id=bill_company_id if add_bill else None,
                    bill_register=wanted.register if add_bill else None)

    def run(conversation: list[dict], effort: str, transcript: list | None = None) -> Reply:
        out = provider.run(conversation, instructions, tools, emit, effort, **({"transcript": transcript} if transcript else {}))
        reply = out if isinstance(out, Reply) else Reply(*out)
        answer = indian_digits(reply.text)  # the model sometimes writes 2,328,413.00; accounts here read 23,28,413.00
        answer = strip_context(answer) or EMPTY_ANSWER  # a copied <context> block is neither checked nor kept
        tools.check_cancelled()
        if not provider.streams:
            emit({"type": "delta", "text": answer})
        elif answer != reply.text:  # the streamed draft showed a <context> block (or Western digits): replace it
            emit({"type": "reset"})
            emit({"type": "delta", "text": answer})
        return dataclasses.replace(reply, text=answer, complete=reply.complete and not is_fallback(answer))

    try:
        if add_files:  # the app adds what the person asked for before the answer, which then reports it
            added, handled = _add_files(tools, wanted)
            documents = f"{documents}\n\n{added}" if documents else added
            # Sheets not added this time (another file, or a sheet not asked for) keep their offer and buttons.
            pending = [p for p in pending if p["table"] not in handled]
        if pending:
            documents = f"{documents}\n\n{pending_text(pending)}" if documents else pending_text(pending)
        if combined is not None:
            documents = f"{documents}\n\n{combined()}" if documents else combined()
        # Data ready by the time the model asks for it; started after the documents so it does not slow them down.
        threading.Thread(target=tools.prepare, daemon=True).start()
        emit({"type": "step", "text": "Reading your entries…"})
        instructions, dictionary = build_instructions(sheets, registers=bool(extra and "registers" in extra), documents=documents,
                                                      books=bool(extra and "book_sales" in extra), books_note=unreadable_note(extra))
        if add_bill:
            said = f" as a {'sale' if wanted.register == 'sales' else 'purchase'}" if wanted.register else ""
            instructions += (f"\n\nThe person asks to save the bill they typed{said}: call add_bill now, once per bill, "
                             "without asking anything first.")
        elif checked and wanted is None:
            instructions += ("\n\nThe app could not read whether the person asked to add something to the books, so "
                             "nothing was added. If they asked, say so in one line and ask them to send it again.")
        language = reply_language(messages)
        if language:  # last, so the long start of the instructions stays the same and is served from the prompt cache
            instructions += f"\n\nThe person's latest message is in {language}: reply in {language}."
        # Figures may come from what the person wrote, the data dictionary (computed by the app) or this answer's
        # tool results. Earlier answers are not evidence: a wrong figure there must not verify a repeat of it.
        known_text = [m["content"] for m in messages if m["role"] == "user"] + [dictionary]
        reply = run(messages, provider.effort())
        check = verify(reply.text, known_values(known_text, tools.result_rows()))
        corrected = False
        if check["status"] == "unverified":
            emit({"type": "reset", "text": f"Double-checking {', '.join(check['unverified'][:3])}…"})
            repair = REPAIR_PROMPT.format(figures=", ".join(check["unverified"]))
            retry = messages + [{"role": "assistant", "content": reply.text}, {"role": "user", "content": repair}]
            # The first round's tool calls and results go along, so only the flagged figures are recomputed.
            repaired = run(retry, provider.repair_effort(), reply.transcript)
            if repaired.complete or not reply.complete:
                reply, corrected = repaired, True
                check = verify(reply.text, known_values(known_text, tools.result_rows()))
            else:  # the correction round failed (step limit, refusal): keep the first answer, flagged
                emit({"type": "reset"})
                emit({"type": "delta", "text": reply.text})
    except Exception:
        if cancel is not None and cancel.is_set():
            raise Cancelled() from None  # e.g. the model stream was closed under the request
        raise
    finally:
        tools.close()

    result = {
        "answer": reply.text,
        "queries": tools.queries,
        "calculations": tools.calculations,
        "formula_checks": tools.formula_checks,
        "analyses": tools.analyses,
        "imports": tools.imports,
        # Still not in the books (the sheets this answer added, or left out as repeats, are not among them).
        "pending_registers": pending,
        "verification": {**check, "corrected": corrected},
        "model": reply.model,
        "provider": provider.id,
        "cached": False,
    }
    if cancel is not None and cancel.is_set():
        raise Cancelled()  # stopped as it finished: nobody saw this answer, so it is not kept either
    # An answer that added to the books reports what that call did; asked again, the books must be asked again. So is an
    # answer to a request to add: asked again, it adds.
    if check["status"] != "unverified" and reply.complete and not tools.added_to_books and not (wanted and wanted.add):
        with _ANSWERS_LOCK:
            _ANSWERS[key] = copy.deepcopy(result)
            while len(_ANSWERS) > _ANSWERS_MAX:
                _ANSWERS.popitem(last=False)
    return result
