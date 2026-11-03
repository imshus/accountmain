"""Live voice conversations with GPT: the voice agent the app's mic opens (asked for on 2026-10-28: "a dynamic voice
agent with every API and system the app has; clicking the mic starts it").

The app sends its WebRTC offer here; the backend starts the call with OpenAI's Realtime API (its key and the session's
settings stay on the server) and returns OpenAI's answer, so the voice then flows between the phone and OpenAI
directly. For anything about the books or the shared files the voice model calls the app's one tool, ask_books, which
the app runs as a typed chat message (the same chat: the intent check that adds files and bills to sales or purchases,
the books tables, analysis, reports, checked figures) and then speaks that checked answer.
"""

from __future__ import annotations

import logging
import os
import threading

import openai

from . import config
from .llm import gpt

MODEL = os.getenv("OPENAI_VOICE_MODEL", "gpt-realtime-2.1").strip() or "gpt-realtime-2.1"
VOICE = os.getenv("OPENAI_VOICE", "marin").strip() or "marin"
TRANSCRIBE_MODEL = os.getenv("OPENAI_VOICE_TRANSCRIBE_MODEL", "gpt-transcribe").strip() or "gpt-transcribe"
REASONING_EFFORT = os.getenv("OPENAI_VOICE_REASONING_EFFORT", "low").strip() or "low"
MAX_SDP_BYTES = 64 * 1024
# One attempt, no retry: the app waits 30 s for the answer, so a slow start fails here first with a clear reason.
TIMEOUT_SECONDS = 20
# The app ends a call after 15 minutes (or 3 quiet ones); the server hangs up any call still open a little later, so a
# call the app lost track of (killed, or a client that never hangs up) cannot run up the OpenAI bill.
MAX_CALL_SECONDS = 20 * 60
# Per reply, reasoning and the tool call included: a spoken answer is one or two sentences.
MAX_OUTPUT_TOKENS = 4096

log = logging.getLogger(__name__)

INSTRUCTIONS = """You are the voice of Accounts.ai, the accounting app of an Indian jewellery business, talking with its owner or staff on their phone.
- Speak the language the person speaks (Hinglish, Hindi, English, Gujarati, Marathi, Punjabi, Bengali, Tamil, Telugu...), warmly and briefly: one or two short sentences. Say amounts the Indian way (lakh, crore) and grams with "gram".
- For ANYTHING about their business, books or files, call ask_books with the person's request in their own words and language, complete with every detail they said: questions (sales, purchases, stock, a party's bills, totals, GST, reports, what a shared file holds) and things to do (add or save a bill they describe to sales or purchases, add a shared file to the books). The app does it and returns a checked answer. Never answer a business figure yourself and never invent one.
- A bill: pass everything said (party, item, gross or net weight, purity or karat, diamond weight and rate, labour rate, date, bill number). Do not ask them to confirm and do not ask "sales or purchase?": the app decides and adds it.
- When ask_books returns, say its answer briefly in the person's language: the key figures, the bill number, what was added. If it reports a problem, say it simply.
- Greetings, small talk or how to use the app: answer yourself, briefly.
- If you did not catch what they said, ask them to say it again."""

ASK_BOOKS = {
    "type": "function",
    "name": "ask_books",
    "description": ("Ask the Accounts.ai app anything about the business's books and shared files, or ask it to do "
                    "something (add a bill to sales or purchases, add a shared file to the books). The app answers as "
                    "its chat does, with checked figures, and does what was asked without asking anything."),
    "parameters": {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": ("The person's request in their own words and language, complete with every detail "
                                "they gave, e.g. 'Ramesh ko 5 gram 18 carat ring becha, labour 500 per gram' or "
                                "'aaj ki total sale kitni hui'."),
            },
        },
        "required": ["request"],
        "additionalProperties": False,
    },
}


class VoiceError(Exception):
    """The voice call could not be started; ``message`` is shown in the app."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def session() -> dict:
    """The Realtime session the call starts with."""
    return {
        "type": "realtime",
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "audio": {
            "input": {
                "transcription": {"model": TRANSCRIBE_MODEL},  # the person's words, shown as captions
                "turn_detection": {"type": "semantic_vad", "eagerness": "auto"},  # they may interrupt the voice
                "noise_reduction": {"type": "near_field"},  # a phone held close
            },
            "output": {"voice": VOICE},
        },
        "tools": [ASK_BOOKS],
        "tool_choice": "auto",
        "parallel_tool_calls": False,  # the app answers one request at a time
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": REASONING_EFFORT},
    }


def _hang_up_later(call_id: str) -> None:
    """End the call ``call_id`` after MAX_CALL_SECONDS if it is still open (best effort)."""

    def hang_up() -> None:
        try:
            gpt._client().with_options(timeout=TIMEOUT_SECONDS, max_retries=0).realtime.calls.hangup(call_id)
        except openai.NotFoundError:
            pass  # already ended
        except Exception as exc:  # noqa: BLE001 - a timer thread has no caller to tell
            log.warning("Could not hang up voice call %s: %s", call_id, exc)

    timer = threading.Timer(MAX_CALL_SECONDS, hang_up)
    timer.daemon = True
    timer.start()


def answer(sdp: str) -> str:
    """OpenAI's SDP answer to the app's WebRTC offer ``sdp``, for a call started with session(). Raises VoiceError."""
    if not config.openai_configured():
        raise VoiceError(503, "GPT is not set up on the server: add OPENAI_API_KEY to backend/.env.")
    sdp = (sdp or "").strip()
    if not sdp.startswith("v=0") or len(sdp.encode()) > MAX_SDP_BYTES:
        raise VoiceError(400, "That is not a voice call offer from the app.")
    client = gpt._client().with_options(timeout=TIMEOUT_SECONDS, max_retries=0)  # the same warm connection
    try:
        reply = client.realtime.calls.create(sdp=sdp + "\r\n", session=session())
    except openai.APITimeoutError:
        raise VoiceError(504, "OpenAI took too long to start the voice call. Try again.") from None
    except openai.APIStatusError as exc:
        reason = str(getattr(exc, "message", "") or "")[:200]
        raise VoiceError(502, f"OpenAI did not start the voice call ({exc.status_code}){': ' + reason if reason else ''}.") from None
    except openai.APIConnectionError:
        raise VoiceError(502, "The server could not reach OpenAI to start the voice call. Try again.") from None
    # The call's address, e.g. /v1/realtime/calls/rtc_abc123: its last part is the id to hang up with.
    call_id = reply.response.headers.get("location", "").rstrip("/").rsplit("/", 1)[-1]
    if call_id and call_id != "calls":
        _hang_up_later(call_id)
    else:
        log.warning("OpenAI gave no call id for the voice call; it will not be hung up after %s s", MAX_CALL_SECONDS)
    return reply.content.decode("utf-8", "replace")
