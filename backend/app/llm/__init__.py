"""Chat about an upload with GPT-6 Luna or Claude.

Both models get the same instructions and the same tools: ``analyse`` (totals and
breakdowns on exact decimals, no SQL), ``run_sql`` (read-only DuckDB, limited to the tables
of the selected upload), ``calculate`` (exact decimal arithmetic) and ``check_formula``; in a chat over shared files with
a company chosen, also ``add_to_books`` (posts a shared sheet to that company's books). After each answer every figure in it is checked against what the tools
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

from .. import config
from ..duck import sheet_key
from . import claude, gpt
from .common import (EMPTY_ANSWER, REPAIR_PROMPT, CancelEvent, Cancelled, LLMError, Reply, Toolbox, build_instructions,
                     is_fallback, pending_text, reply_language, strip_context)
from .verify import indian_digits, known_values, verify

__all__ = ["CancelEvent", "Cancelled", "LLMError", "chat", "default_provider", "provider_status", "strip_context"]

_MODEL_LABELS = {
    "gpt-6-luna": "GPT-6 Luna",
    "gpt-6-sol": "GPT-6 Sol",
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-sonnet-5-5": "Claude Sonnet 5.5",
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
    "anthropic": Provider(
        "anthropic", config.ANTHROPIC_MODEL, "ANTHROPIC_API_KEY", config.anthropic_configured, claude.chat,
        lambda: config.ANTHROPIC_EFFORT, lambda: config.ANTHROPIC_REPAIR_EFFORT, False,
    ),
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
    return (provider.id, provider.model, provider.effort(), tuple(sheet_key(s) for s in sheets), extra_keys, documents,
            combined, company_id, json.dumps(pending or [], sort_keys=True), json.dumps(messages, ensure_ascii=False))


def default_provider() -> str:
    """The configured LLM_PROVIDER, else whichever provider has a key."""
    preferred = PROVIDERS.get(config.LLM_PROVIDER, PROVIDERS["openai"])
    if preferred.configured():
        return preferred.id
    return next((p.id for p in PROVIDERS.values() if p.configured()), preferred.id)


def provider_status() -> list[dict]:
    return [
        {"id": p.id, "label": p.label, "model": p.model, "configured": p.configured(), "key_name": p.key_name}
        for p in PROVIDERS.values()
    ]


def chat(provider_id: str | None, messages: list[dict], sheets: list[dict], extra: dict | None = None, emit=None,
         fresh: bool = False, documents: str | None = None, combined: Callable[[], str] | None = None,
         cancel: threading.Event | None = None, company_id: int | None = None, pending: list[dict] | None = None) -> dict:
    """Answer the conversation. ``emit`` receives live progress: steps, answer text as it is written,
    and "reset" when a draft is replaced (a correction round). ``combined`` returns the registers comparison
    added to ``documents``; it is called only when the answer is not remembered (it can take seconds).
    With ``company_id`` (an existing company) and sheets, the model may post a sheet to that company's books.
    ``pending``: shared sheets not in that company's books whose register the person has not said; the answer asks,
    and returns them as pending_registers unless it added a sheet to the books.
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
    # The answer the latest message replies to: if it asked which register, naming both, the person may overrule the detection.
    previous = messages[-2]["content"] if len(messages) > 1 and messages[-2]["role"] == "assistant" else ""
    tools = Toolbox({sheet["table_name"]: sheet for sheet in sheets}, extra, emit=emit, cancel=cancel, company_id=company_id,
                    request=latest, previous=strip_context(previous))

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
        if pending:
            documents = f"{documents}\n\n{pending_text(pending)}" if documents else pending_text(pending)
        if combined is not None:
            documents = f"{documents}\n\n{combined()}" if documents else combined()
        # Data ready by the time the model asks for it; started after the documents so it does not slow them down.
        threading.Thread(target=tools.prepare, daemon=True).start()
        emit({"type": "step", "text": "Reading the question…"})
        instructions, dictionary = build_instructions(sheets, registers=bool(extra and "registers" in extra), documents=documents)
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
        # Still to be added once the person says which register; nothing is pending after an answer that added a sheet.
        "pending_registers": [] if tools.imports else pending,
        "verification": {**check, "corrected": corrected},
        "model": reply.model,
        "provider": provider.id,
        "cached": False,
    }
    if cancel is not None and cancel.is_set():
        raise Cancelled()  # stopped as it finished: nobody saw this answer, so it is not kept either
    # An answer that added to the books reports what that call did; asked again, the books must be asked again.
    if check["status"] != "unverified" and reply.complete and not tools.added_to_books:
        with _ANSWERS_LOCK:
            _ANSWERS[key] = copy.deepcopy(result)
            while len(_ANSWERS) > _ANSWERS_MAX:
                _ANSWERS.popitem(last=False)
    return result
