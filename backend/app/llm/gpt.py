"""OpenAI models (GPT-6 Luna by default) through the Responses API with function calling."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import openai

try:  # openai 3.x (Python 3.10+) runs on httpx2
    import httpx2 as httpx
    _HttpClient = openai.DefaultHttpx2Client
except ImportError:  # openai 2.x, the last line for Python 3.9, runs on httpx
    import httpx
    _HttpClient = openai.DefaultHttpxClient

from .. import analysis, config
from .common import (
    ANALYSE_PARAMS,
    ANALYSE_TOOL_DESCRIPTION,
    CALC_EXPRESSION_DESCRIPTION,
    CALC_TOOL_DESCRIPTION,
    CUT_OFF_NOTE,
    DECLINED,
    EMPTY_ANSWER,
    FORMULA_PARAMS,
    FORMULA_TOOL_DESCRIPTION,
    MAX_TOOL_ROUNDS,
    NEEDS_MORE_STEPS,
    NO_ROOM,
    SQL_QUERY_DESCRIPTION,
    SQL_TOOL_DESCRIPTION,
    LLMError,
    Reply,
    Toolbox,
    closing_on_cancel,
    tool_error,
)

# OpenAI recommends reserving at least 25,000 tokens for reasoning plus the visible answer.
MAX_OUTPUT_TOKENS = 32_000


def _function(name: str, description: str, params: dict[str, tuple[str, str]]) -> dict:
    """params: name -> (JSON type, description). Strict mode: every parameter is required."""
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {p: {"type": t, "description": d} for p, (t, d) in params.items()},
            "required": list(params),
            "additionalProperties": False,
        },
        "strict": True,
    }


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


ANALYSE_TOOL = {
    "type": "function",
    "name": "analyse",
    "description": ANALYSE_TOOL_DESCRIPTION,
    "parameters": _object({
        "table": {"type": "string", "description": ANALYSE_PARAMS["table"]},
        "measures": {"type": "array", "description": ANALYSE_PARAMS["measures"], "items": _object({
            "agg": {"type": "string", "enum": list(analysis.AGGS)}, "column": {"type": "string"}})},
        "group_by": {"type": "array", "description": ANALYSE_PARAMS["group_by"], "items": _object({
            "column": {"type": "string"}, "bucket": {"type": "string", "enum": list(analysis.BUCKETS)}})},
        "filters": {"type": "array", "description": ANALYSE_PARAMS["filters"], "items": _object({
            "column": {"type": "string"}, "op": {"type": "string", "enum": list(analysis.OPS)}, "value": {"type": "string"},
            "value2": {"type": "string"}, "values": {"type": "array", "items": {"type": "string"}}})},
        "sort": {"type": "string", "enum": list(analysis.SORTS), "description": ANALYSE_PARAMS["sort"]},
        "limit": {"type": "integer", "description": ANALYSE_PARAMS["limit"]},
        "across": {"type": "boolean", "description": ANALYSE_PARAMS["across"]},
    }),
    "strict": True,
}

TOOLS = [
    ANALYSE_TOOL,
    _function("run_sql", SQL_TOOL_DESCRIPTION, {"query": ("string", SQL_QUERY_DESCRIPTION)}),
    _function("calculate", CALC_TOOL_DESCRIPTION, {"expression": ("string", CALC_EXPRESSION_DESCRIPTION)}),
    _function("check_formula", FORMULA_TOOL_DESCRIPTION, {
        "table": ("string", FORMULA_PARAMS["table"]),
        "target_column": ("string", FORMULA_PARAMS["target_column"]),
        "expression": ("string", FORMULA_PARAMS["expression"]),
        "tolerance": ("number", FORMULA_PARAMS["tolerance"]),
    }),
]

_QUOTA_CODES = {"insufficient_quota", "credit_balance_exhausted", "organization_usage_limit_exceeded"}


def _run_call(tools: Toolbox, call) -> str:
    try:
        args = json.loads(call.arguments)
        if call.name == "analyse":
            return tools.analyse(args)
        if call.name == "run_sql":
            return tools.run_sql(args["query"])
        if call.name == "calculate":
            return tools.calculate(args["expression"])
        if call.name == "check_formula":
            return tools.check_formula(args["table"], args["target_column"], args["expression"], float(args["tolerance"]))
    except Exception as exc:  # noqa: BLE001 - the real reason goes back to the model, which fixes its call
        return tool_error(exc)
    return f"Error: unknown tool {call.name}."


def _answer(response) -> tuple[str, bool]:
    """(answer, complete): a refusal, a cut-off or an empty answer is shown but marked incomplete."""
    text = response.output_text.strip()
    if not text:
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if part.type == "refusal":
                        return DECLINED, False
    if response.status == "incomplete":
        reason = response.incomplete_details.reason if response.incomplete_details else None
        if reason == "content_filter":
            return DECLINED, False
        if not text:
            return NO_ROOM, False
        return f"{text}{CUT_OFF_NOTE}", False
    return (text, True) if text else (EMPTY_ANSWER, False)


# Tool calls run side by side: several analyses or queries asked for in one step finish together.
_TOOL_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ai-tool")


def _streamed_round(client, emit, on_call, cancel=None, **request):
    """One model call, streamed: answer text is passed on as it arrives, and each tool call is handed to
    ``on_call`` the moment it is complete, while the rest of the response is still arriving. If the answer
    is cancelled meanwhile, the stream is closed at once, so the model stops generating (and billing) tokens.
    Returns (response, wrote_text)."""
    response, wrote = None, False
    with client.responses.create(stream=True, **request) as stream, closing_on_cancel(cancel, stream.close):
        for event in stream:
            if event.type == "response.output_text.delta":
                emit({"type": "delta", "text": event.delta})
                wrote = True
            elif event.type == "response.output_item.done" and getattr(event.item, "type", None) == "function_call":
                on_call(event.item)
            elif event.type in ("response.completed", "response.incomplete"):
                response = event.response
            elif event.type == "response.failed":
                error = getattr(event.response, "error", None)
                raise LLMError(502, f"OpenAI could not finish the answer: {getattr(error, 'message', 'unknown error')}")
            elif event.type == "error":
                raise LLMError(502, f"OpenAI returned an error: {getattr(event, 'message', 'unknown error')}")
    if response is None:
        raise LLMError(502, "OpenAI stopped before finishing the answer. Try again.")
    return response, wrote


_CLIENT: openai.OpenAI | None = None
_WARMED_AT = 0.0
_WARM_LOCK = threading.Lock()


def _client() -> openai.OpenAI:
    """One client for the whole backend whose HTTPS connection to OpenAI stays open between questions.
    The SDK drops idle connections after 5 s, and a new handshake costs about half a second, so idle
    connections are kept for 90 s instead."""
    global _CLIENT
    if _CLIENT is None:
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=90)
        # A stalled answer fails within minutes instead of the SDK's 10 minutes x 3 tries.
        _CLIENT = openai.OpenAI(http_client=_HttpClient(limits=limits), timeout=httpx.Timeout(120.0, connect=10.0), max_retries=1)
    return _CLIENT


def warm_up() -> None:
    """Open the connection to OpenAI before a question is sent: a free model lookup, no tokens.
    Called when the backend starts and when someone starts typing a question (at most every 30 s)."""
    global _WARMED_AT
    with _WARM_LOCK:
        if time.monotonic() - _WARMED_AT < 30:
            return
        _WARMED_AT = time.monotonic()
    try:
        _client().models.retrieve(config.OPENAI_MODEL)
    except Exception:  # noqa: BLE001 - warming is best effort; the question itself reports real errors
        pass


def chat(messages: list[dict], instructions: str, tools: Toolbox, emit=None, effort: str | None = None,
         transcript: list | None = None) -> Reply:
    """``transcript`` (from an earlier Reply) continues that exchange, tool calls and results included, with
    the last of ``messages`` as the new user message."""
    emit = emit or (lambda _event: None)
    client = _client()
    if transcript:
        items: list = [*transcript, {"role": "user", "content": messages[-1]["content"]}]
    else:
        items = [{"role": m["role"], "content": m["content"]} for m in messages]
    model = config.OPENAI_MODEL
    options = {"service_tier": config.OPENAI_SERVICE_TIER} if config.OPENAI_SERVICE_TIER else {}
    if config.OPENAI_VERBOSITY:
        options["text"] = {"verbosity": config.OPENAI_VERBOSITY}
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            running: dict[str, Future] = {}

            def start(call):
                if call.call_id not in running:
                    running[call.call_id] = _TOOL_POOL.submit(_run_call, tools, call)

            tools.check_cancelled()
            response, wrote = _streamed_round(
                client, emit, start, tools.cancel,
                model=model,
                instructions=instructions,
                input=items,
                tools=TOOLS,
                reasoning={"effort": effort or config.OPENAI_REASONING_EFFORT},
                max_output_tokens=MAX_OUTPUT_TOKENS,
                prompt_cache_key=tools.cache_key,
                parallel_tool_calls=True,
                **options,
            )
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                answer, complete = _answer(response)
                return Reply(answer, response.model, complete, [*items, *response.output])
            if wrote:
                emit({"type": "reset"})  # text written before a tool call was the model thinking aloud
            # Reasoning and function-call items go back with the results so the model keeps its train of thought.
            items += response.output
            for call in calls:
                start(call)  # any call the stream did not announce separately
            for call in calls:
                items.append({"type": "function_call_output", "call_id": call.call_id, "output": running[call.call_id].result()})
    except openai.AuthenticationError as exc:
        raise LLMError(502, "The OpenAI API key was rejected. Check OPENAI_API_KEY in backend/.env.") from exc
    except openai.PermissionDeniedError as exc:
        raise LLMError(502, f"The OpenAI API key cannot use model {model}.") from exc
    except openai.NotFoundError as exc:
        raise LLMError(502, f"OpenAI model {model} was not found. Check OPENAI_MODEL.") from exc
    except openai.RateLimitError as exc:
        if getattr(exc, "code", None) in _QUOTA_CODES or "limit_exceeded" in str(getattr(exc, "code", "")):
            raise LLMError(402, "The OpenAI account is out of credit or over its spend limit.") from exc
        raise LLMError(429, "OpenAI is rate limiting requests. Try again in a minute.") from exc
    except openai.APIStatusError as exc:
        raise LLMError(502, f"OpenAI returned an error ({exc.status_code}): {exc.message}") from exc
    except openai.APIConnectionError as exc:
        raise LLMError(502, "Could not reach OpenAI. Check the internet connection.") from exc
    return Reply(NEEDS_MORE_STEPS, model, False, items)
