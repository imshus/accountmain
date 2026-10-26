"""Accounts.ai backend: upload spreadsheets, profile them, keep the books, and query them with SQL or AI."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout  # the builtin TimeoutError only from Python 3.11
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import OperationalError

from datetime import date

from . import analysis, books, classify, cloud, config, database, detect, editing, llm, mongo_sync, reports
from .accounts import api as accounts_api
from .accounts import db as _accounts_tables  # noqa: F401  (registers the books tables before create_all)
from .accounts import imports as accounts_imports
from .accounts import service as accounts_service
from .analytics import profile_sheet
from .calc import CalcError, evaluate_number, format_decimal
from .duck import Session, cached, sheet_key
from .excel_loader import UploadError, read_workbook
from .llm import followups
from .llm.common import describe_tables, says_register, warm_tables
from .schemas import (
    AddRowRequest,
    AnalysisRequest,
    BookDetail,
    BookRegistersRequest,
    BookSummary,
    CreateBookRequest,
    CalcRequest,
    CalcResult,
    CHAT_ID,
    CHAT_SCOPE,
    ChatList,
    ChatRequest,
    ChatResponse,
    ChatSaved,
    ColumnCalcRequest,
    ColumnCalcResult,
    CloudSummary,
    Conversation,
    DatasetDetail,
    DocumentsRequest,
    FilesChatRequest,
    Followups,
    FollowupsRequest,
    DatasetSummary,
    GstNetOut,
    Health,
    MongoSummary,
    NotesRequest,
    QueryOut,
    Report,
    RowsPage,
    SetupOut,
    SetupRequest,
    SheetDetail,
    SqlRequest,
    chat_time,
)

# Older turns beyond this are dropped; the table context is resent every turn anyway.
MAX_CHAT_MESSAGES = 20


@asynccontextmanager
async def lifespan(_app: FastAPI):
    problem = database.storage_problem()
    if problem:
        print(problem)
    try:
        database.init_db()
    except OperationalError as exc:
        # A read-only data folder: still start, so the books can be read and every save explains how to fix it.
        if "readonly database" not in str(exc):
            raise
        if not problem:
            print(f"The database is read-only, so nothing can be saved until that is fixed: {exc}")
    cloud.resume()  # copies to Supabase that were still waiting when the backend stopped
    mongo_sync.start()  # the live copy of the records in MongoDB, when set up
    if config.openai_configured():
        threading.Thread(target=llm.gpt.warm_up, daemon=True).start()  # the first question skips the handshake
    yield


class _ErrorsAsJson:
    """An unexpected error becomes a JSON 500 inside CORSMiddleware, so the app can read the reason. Starlette's own
    500 page comes from the outermost layer without CORS headers, and the app would only see "cannot reach the backend"."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def tracked_send(message):
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception as exc:
            logging.getLogger("uvicorn.error").exception("%s %s failed", scope.get("method"), scope.get("path"))
            if started:  # part of the answer is already out (a streamed chat): nothing else can be sent
                raise
            if "readonly database" in str(exc):
                detail = database.storage_problem() or "The server cannot save: its database is read-only for the backend's user."
            else:
                detail = f"The server hit an error: {type(exc).__name__}: {exc}"[:330]
            await JSONResponse({"detail": detail}, status_code=500)(scope, receive, send)


class _ChatBodyLimit:
    """A conversation sent to PUT /api/chats is refused (413) as soon as it is known to be too large: from its
    Content-Length, or while a body without one arrives. It is never read whole and parsed first."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "PUT" or not scope["path"].startswith("/api/chats/"):
            return await self.app(scope, receive, send)
        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and int(length) > MAX_CHAT_BODY:
            return await JSONResponse({"detail": CHAT_TOO_LARGE}, status_code=413)(scope, receive, send)
        received = 0

        async def counted():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > MAX_CHAT_BODY:
                raise HTTPException(status_code=413, detail=CHAT_TOO_LARGE)
            return message

        await self.app(scope, counted, send)


app = FastAPI(title="Accounts.ai API", version="0.1.0", lifespan=lifespan)
app.add_middleware(_ErrorsAsJson)  # added first, so it runs inside CORSMiddleware
app.add_middleware(_ChatBodyLimit)  # inside CORSMiddleware too, so the app can read its 413
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(accounts_api.router)


def _dataset_or_404(dataset_id: int) -> dict:
    dataset = database.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return dataset


def _sheet_or_404(dataset_id: int, table_name: str) -> dict:
    sheet = next((s for s in _dataset_or_404(dataset_id)["sheets"] if s["table_name"] == table_name), None)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Sheet not found.")
    return sheet


def _sheet_detail(sheet: dict) -> dict:
    preview = database.read_preview(sheet["table_name"], config.PREVIEW_ROWS)
    split = json.loads(preview.to_json(orient="split", index=False, date_format="iso"))
    return {
        "sheet_name": sheet["sheet_name"],
        "table_name": sheet["table_name"],
        "row_count": sheet["row_count"],
        "profile": sheet["profile"],
        "preview": {"columns": split["columns"], "rows": split["data"]},
    }


def _fresh_sheet(dataset_id: int, table_name: str) -> dict:
    return _sheet_detail(_sheet_or_404(dataset_id, table_name))


def _detail(dataset: dict) -> dict:
    sheets = [_sheet_detail(sheet) for sheet in dataset["sheets"]]
    return {**{k: dataset[k] for k in ("id", "filename", "size_bytes", "uploaded_at")}, "sheets": sheets,
            "cloud": cloud.status_of(dataset["id"])}


@app.get("/api/health", response_model=Health)
def health():
    return {"status": "ok", "providers": llm.provider_status(), "default_provider": llm.default_provider(),
            "cloud": cloud.summary(), "mongo": mongo_sync.summary(), "storage_problem": database.storage_problem()}


@app.post("/api/upload", response_model=DatasetDetail, status_code=201)
def upload(file: UploadFile = File(...)):
    filename = Path(file.filename or "upload").name
    if Path(filename).suffix.lower() not in config.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(config.ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Upload one of: {allowed}.")

    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"File is larger than {config.MAX_UPLOAD_MB} MB.")
    if not content:
        raise HTTPException(status_code=400, detail="The file is empty.")

    try:
        parsed = read_workbook(content, filename)
    except UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sheets = [(s.name, s.frame, profile_sheet(s.frame, s.labels, s.checks)) for s in parsed]
    # Filed under the register it clearly is, else unsorted until a sheet of it is added to the books.
    register = detect.upload_register([{"sheet_name": name, "row_count": len(frame), "profile": profile}
                                       for name, frame, profile in sheets], filename)
    dataset_id = database.save_dataset(filename, len(content), sheets, register)
    try:
        cloud.enqueue(dataset_id, filename, content, register)  # background copy to Supabase, when set up
    except Exception as exc:  # noqa: BLE001 - the upload has succeeded; the copy must never turn it into an error
        print(f"Supabase copy of upload {dataset_id} not queued ({type(exc).__name__}).")
    mongo_sync.touch("upload", dataset_id)  # after enqueue, so MongoDB's copy shows the Supabase copy as waiting
    return _detail(_dataset_or_404(dataset_id))


@app.get("/api/cloud", response_model=CloudSummary)
def cloud_summary():
    """Copies of uploaded documents in Supabase Storage: how many are sent, waiting or failed."""
    return cloud.summary()


@app.post("/api/cloud/retry")
def cloud_retry():
    """Send every failed copy again (e.g. after fixing the Supabase key in backend/.env and restarting)."""
    if not cloud.configured():
        raise HTTPException(status_code=409, detail="Supabase is not set up: add SUPABASE_URL and SUPABASE_SERVICE_KEY to backend/.env.")
    return {"retried": cloud.retry_failed()}


@app.get("/api/mongo", response_model=MongoSummary)
def mongo_summary():
    """The live copy of the records in MongoDB: how many uploads and conversations are sent, waiting or failed."""
    return mongo_sync.summary()


@app.post("/api/mongo/retry")
def mongo_retry():
    """Send every failed record again (e.g. after fixing MONGODB_URI in backend/.env and restarting)."""
    if not mongo_sync.configured():
        raise HTTPException(status_code=409, detail="MongoDB is not set up: add MONGODB_URI to backend/.env and restart the backend.")
    return {"retried": mongo_sync.retry_failed()}


@app.get("/api/datasets", response_model=list[DatasetSummary])
def list_datasets():
    return database.list_datasets()


@app.get("/api/datasets/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: int):
    return _detail(_dataset_or_404(dataset_id))


@app.delete("/api/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int):
    if not database.delete_dataset(dataset_id):
        raise HTTPException(status_code=404, detail="Upload not found.")
    mongo_sync.touch("upload", dataset_id)
    _delete_chats(f"ds-{dataset_id}")


def _sql(sheets: list[dict], sql: str, extra: dict | None = None) -> dict:
    """Run a person's read-only SELECT on DuckDB over these sheets."""
    try:
        with Session(sheets, extra) as session:
            result = session.query(sql)
    except database.QueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"sql": sql, **result.as_dict()}


def _analyse(sheets: list[dict], body: AnalysisRequest, extra: dict | None = None) -> dict:
    try:
        with Session(sheets, extra) as session:
            return analysis.run(session, body.model_dump())
    except analysis.AnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _fields(sheets: list[dict], extra: dict | None = None, titles: dict[str, str] | None = None) -> list[dict]:
    """Every table the Analyse screen can use, with its columns (kind and exact decimals)."""
    with Session(sheets, extra) as session:
        return [{"table": table, "title": (titles or {}).get(table) or session.titles.get(table, table),
                 "fields": [f.as_dict() for f in fields]} for table, fields in session.fields.items()]


@app.post("/api/datasets/{dataset_id}/sql", response_model=QueryOut)
def run_sql(dataset_id: int, body: SqlRequest):
    return _sql(_dataset_or_404(dataset_id)["sheets"], body.sql)


@app.post("/api/datasets/{dataset_id}/analyse")
def analyse_dataset(dataset_id: int, body: AnalysisRequest):
    return _analyse(_dataset_or_404(dataset_id)["sheets"], body)


@app.get("/api/datasets/{dataset_id}/fields")
def dataset_fields(dataset_id: int):
    return _fields(_dataset_or_404(dataset_id)["sheets"])


@app.post("/api/calc", response_model=CalcResult)
def calculate_numbers(body: CalcRequest):
    try:
        return {"expression": body.expression, "result": format_decimal(evaluate_number(body.expression))}
    except CalcError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/datasets/{dataset_id}/sheets/{table_name}/calculate", response_model=ColumnCalcResult)
def calculate_column(dataset_id: int, table_name: str, body: ColumnCalcRequest):
    sheet = _sheet_or_404(dataset_id, table_name)
    try:
        frame, result, stats = editing.calculate(sheet, body.expression)
        out = {"expression": body.expression, "stats": stats, "preview": editing.preview(sheet, body.expression, frame, result)}
        if body.compare_to:
            out["check"] = editing.check_formula(sheet, body.compare_to, body.expression, body.tolerance, frame)
        if body.save_as:
            name = editing.save_column(sheet, body.save_as, result, frame)
            editing.refresh_profile(sheet, {"columns": 1}, {name: body.save_as.strip()})
            mongo_sync.touch("upload", dataset_id)
            out |= {"saved_column": name, "sheet": _fresh_sheet(dataset_id, table_name)}
    except (CalcError, editing.EditError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return out


@app.get("/api/datasets/{dataset_id}/sheets/{table_name}/rows", response_model=RowsPage)
def list_rows(
    dataset_id: int,
    table_name: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: str | None = Query(None, max_length=200),
):
    return editing.list_rows(_sheet_or_404(dataset_id, table_name), offset, limit, search)


@app.post("/api/datasets/{dataset_id}/sheets/{table_name}/rows", response_model=SheetDetail, status_code=201)
def add_row(dataset_id: int, table_name: str, body: AddRowRequest):
    sheet = _sheet_or_404(dataset_id, table_name)
    try:
        editing.add_row(sheet, body.values)
    except editing.EditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    editing.refresh_profile(sheet, {"added": 1})
    mongo_sync.touch("upload", dataset_id)
    return _fresh_sheet(dataset_id, table_name)


@app.delete("/api/datasets/{dataset_id}/sheets/{table_name}/rows/{rowid}", response_model=SheetDetail)
def delete_row(dataset_id: int, table_name: str, rowid: int):
    sheet = _sheet_or_404(dataset_id, table_name)
    try:
        editing.delete_row(sheet, rowid)
    except editing.EditError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    editing.refresh_profile(sheet, {"deleted": 1})
    mongo_sync.touch("upload", dataset_id)
    return _fresh_sheet(dataset_id, table_name)


@app.put("/api/datasets/{dataset_id}/sheets/{table_name}/notes", response_model=SheetDetail)
def save_notes(dataset_id: int, table_name: str, body: NotesRequest):
    editing.save_notes(_sheet_or_404(dataset_id, table_name), body.notes)
    mongo_sync.touch("upload", dataset_id)
    return _fresh_sheet(dataset_id, table_name)


def _setup(sheet: dict) -> dict:
    profile = sheet["profile"]
    return {
        "roles": reports.ROLES,
        "mapping": reports.effective_mapping(profile),
        "detected": reports.detect_mapping(profile),
        "classification": profile.get("classification") or {},
        "groups": list(classify.GROUPS),
        "reports": reports.KINDS,
    }


@app.get("/api/datasets/{dataset_id}/sheets/{table_name}/setup", response_model=SetupOut)
def get_setup(dataset_id: int, table_name: str):
    return _setup(_sheet_or_404(dataset_id, table_name))


@app.put("/api/datasets/{dataset_id}/sheets/{table_name}/setup", response_model=SetupOut)
def save_setup(dataset_id: int, table_name: str, body: SetupRequest):
    sheet = _sheet_or_404(dataset_id, table_name)
    if body.mapping is not None and any(role not in reports.ROLES for role in body.mapping):
        raise HTTPException(status_code=400, detail="Unknown column role.")
    if body.classification is not None and any(g and g not in classify.GROUPS for g in body.classification.values()):
        raise HTTPException(status_code=400, detail="Unknown account group.")
    try:
        editing.save_setup(sheet, body.mapping, body.classification)
    except editing.EditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mongo_sync.touch("upload", dataset_id)
    return _setup(_sheet_or_404(dataset_id, table_name))


def _report_frame(sheet: dict):
    """The sheet's table for a report, loaded once per version of the sheet: every edit rewrites the profile, so
    sheet_key changes and an older frame is never used. Each report gets a shallow copy (copy-on-write), so
    nothing it does can change the remembered frame."""
    return cached(("frame", sheet_key(sheet)), lambda: editing.load_frame(sheet)).copy(deep=False)


@app.get("/api/datasets/{dataset_id}/sheets/{table_name}/reports/{kind}", response_model=Report)
def get_report(
    dataset_id: int,
    table_name: str,
    kind: str,
    account: str | None = None,
    start: date | None = None,
    end: date | None = None,
    as_of: date | None = None,
    opening_stock: float = 0.0,
    closing_stock: float = 0.0,
):
    sheet = _sheet_or_404(dataset_id, table_name)
    if kind not in reports.KINDS:
        raise HTTPException(status_code=404, detail="Unknown report.")
    try:
        return reports.build(
            kind, _report_frame(sheet), sheet["profile"], account=account, start=start, end=end, as_of=as_of,
            opening_stock=opening_stock, closing_stock=closing_stock,
        )
    except reports.ReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/datasets/{dataset_id}/gst-net", response_model=GstNetOut)
def gst_net(dataset_id: int, sales: str, purchases: str | None = None):
    """Net GST payable: output tax of the sales register minus input credit of the purchase register."""
    sales_sheet = _sheet_or_404(dataset_id, sales)
    output = reports.gst_heads(_report_frame(sales_sheet), sales_sheet["profile"])
    credit = {}
    if purchases:
        purchase_sheet = _sheet_or_404(dataset_id, purchases)
        credit = reports.gst_heads(_report_frame(purchase_sheet), purchase_sheet["profile"])
    if not output:
        raise HTTPException(status_code=422, detail="The sales sheet has no CGST/SGST/IGST/Cess columns mapped.")
    result = reports.gst_net_payable(output, credit)
    rupees = lambda d: {h: v / 100 for h, v in d.items()}  # noqa: E731
    steps = [
        f"{source.upper()} credit used for {target.upper()}: {amount / 100:,.2f}"
        for source, targets in result["used"].items() for target, amount in targets.items()
    ]
    return {
        "output_tax": rupees({h: output.get(h, 0) for h in ("igst", "cgst", "sgst", "cess")}),
        "input_credit": rupees({h: credit.get(h, 0) for h in ("igst", "cgst", "sgst", "cess")}),
        "cash_payable": rupees(result["cash"]),
        "credit_carried_forward": rupees(result["credit_left"]),
        "total_cash_payable": sum(result["cash"].values()) / 100,
        "steps": steps,
    }


def _chat_messages(body: ChatRequest) -> list[dict]:
    messages = [m.model_dump() for m in body.messages][-MAX_CHAT_MESSAGES:]
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=422, detail="The conversation must end with a user message.")
    return messages


def _stream_chat(run) -> StreamingResponse:
    """Server-sent events while the AI works: steps, the answer as it is written, "reset" when a draft is
    replaced, then "done" with the full checked result (or "error"). ``run(emit, cancel)`` works on its own
    thread; when the person presses Stop or closes the app, ``cancel`` is set: the model stream is closed,
    the next emit raises llm.Cancelled and nothing of that answer is kept."""
    cancel = llm.CancelEvent()

    async def body():
        loop = asyncio.get_running_loop()
        events: asyncio.Queue = asyncio.Queue()

        def put(event: dict | None) -> None:
            try:
                loop.call_soon_threadsafe(events.put_nowait, event)
            except RuntimeError:  # the server is shutting down
                pass

        def emit(event: dict) -> None:
            if cancel.is_set():
                raise llm.Cancelled()
            put(event)

        def work():
            try:
                result = run(emit, cancel)
                put({"type": "done", "result": ChatResponse.model_validate(result).model_dump(mode="json")})
            except llm.Cancelled:
                pass
            except llm.LLMError as exc:
                put({"type": "error", "status": exc.status_code, "message": exc.message})
            except Exception as exc:  # noqa: BLE001 - reported to the person instead of a broken stream
                put({"type": "error", "status": 500, "message": f"The backend hit an error while answering ({type(exc).__name__})."})
            finally:
                put(None)

        threading.Thread(target=work, daemon=True).start()
        try:
            while (event := await events.get()) is not None:
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        finally:
            cancel.set()  # finished, or the client went away (Starlette cancels this generator on disconnect)

    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/ai/warm", status_code=204)
def warm_ai():
    """Called when someone starts typing a question: opens the connection to OpenAI in the background."""
    if config.openai_configured():
        threading.Thread(target=llm.gpt.warm_up, daemon=True).start()


# A sheet counts as a register (stacked into "registers" and compared) only when detected with confidence:
# a low-confidence guess, such as an invoice sheet inside a ledger workbook, would change every total.
_CONFIDENT = ("high", "medium")


def _shared_files(dataset_ids: list[int]) -> tuple[list[dict], list[dict], str, list[dict]]:
    """Sheets of the files shared in a chat; the sales and purchase registers to compare (empty unless there is
    one of each); what each file is (with the evidence) and exactly which sheets the comparison uses."""
    datasets = [_dataset_or_404(i) for i in dict.fromkeys(dataset_ids)]
    documents, found = detect.describe_documents(datasets)
    kinds = {(f["dataset_id"], f["table_name"]): f["kind"] for f in found if f["confidence"] in _CONFIDENT}
    sheets = [{**sheet, "register": kinds.get((d["id"], sheet["table_name"]))} for d in datasets for sheet in d["sheets"]]
    registers = [s for s in sheets if s["register"] in books.REGISTERS]
    if {s["register"] for s in registers} != set(books.REGISTERS):
        registers = []
    note = _registers_note(found, registers)
    return sheets, registers, documents + (f"\n{note}" if note else ""), found


def _registers_note(found: list[dict], registers: list[dict]) -> str:
    """For the AI: which sheets (file + sheet) the comparison combines, and which register-like sheets it leaves out."""
    used = {s["table_name"] for s in registers}
    where = lambda f: f'file "{f["filename"]}", sheet "{f["sheet_name"]}"'  # noqa: E731
    lines = []
    if used:
        lines.append('Sheets combined for the sales vs purchases comparison (<combined>) and the "registers" table, and only these:')
        for kind, label in books.REGISTERS.items():
            parts = [where(f) for f in found if f["table_name"] in used and f["kind"] == kind]
            lines.append(f"- {label} register: " + "; ".join(parts))
            if len(parts) > 1:
                lines.append(f"  These {len(parts)} sheets are added together as one {label.lower()} register. Say so when "
                             "quoting totals, and ask the person to confirm they are separate entries (not copies of each other).")
    doubtful = [f for f in found if f["kind"] in books.REGISTERS and f["confidence"] not in _CONFIDENT]
    if doubtful:
        lines.append("Not combined, because the detection has low confidence (ask the person to confirm what it is): "
                     + "; ".join(f'{where(f)} (possibly a {f["label"].lower()})' for f in doubtful) + ".")
        if not used:
            lines.append('So no comparison was made and there is no "registers" table.')
    return "\n".join(lines)


# Stacking and comparing two big registers takes seconds, so it starts as soon as /api/documents finds the
# pair, and a chat waits for that same job instead of starting another. The pandas-heavy steps run one after
# the other: side by side they only compete for the interpreter and each finishes later.
_JOBS: OrderedDict[tuple, Future] = OrderedDict()
_JOBS_LOCK = threading.Lock()
_JOB_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="prefetch")


def _job(key: tuple, build) -> Future:
    with _JOBS_LOCK:
        job = _JOBS.get(key)
        if job is None or (job.done() and job.exception() is not None):
            job = _JOBS[key] = _JOB_POOL.submit(build)
        _JOBS.move_to_end(key)
        while len(_JOBS) > 32:
            _JOBS.popitem(last=False)
    return job


def _register_jobs(registers: list[dict]) -> tuple[Future, Future]:
    """(both registers stacked, the comparison text), computed once per version of the registers."""
    key = tuple(sheet_key(s) + (s["register"],) for s in registers)
    table = _job(("registers", key), lambda: analysis.register_table(registers))
    # Submitted after the table, so waiting for it here can never hold up the queue.
    return table, _job(("combined", key), lambda: (table.result(), books.combined_text(registers))[1])


def _prefetch(sheets: list[dict], registers: list[dict]) -> None:
    """Get everything the first question needs ready while the person types it: the registers comparison and,
    alongside it, the data dictionary, then the DuckDB tables (a chat that starts meanwhile waits for these
    instead of repeating them)."""
    jobs = _register_jobs(registers) if registers else None

    def warm():
        describe_tables(sheets)  # mostly SQLite queries, which overlap well with the comparison
        stacked = jobs[0].result() if jobs else None
        if jobs:
            jobs[1].result()
        warm_tables(sheets, {"registers": stacked} if stacked else None)

    _job(("warm", tuple(sheet_key(s) + (s["register"],) for s in sheets)), warm)


def _waiter(emit, cancel):
    """Waits for a register job: says once that the registers are being compared, and stops waiting (the job
    carries on for the next question) when the answer is cancelled."""
    told = False

    def wait(job: Future):
        nonlocal told
        if not job.done() and not told:
            told = True
            emit({"type": "step", "text": "Comparing the sales and purchase registers…"})
        while True:
            try:
                return job.result(timeout=0.2)
            except FutureTimeout:
                if cancel.is_set():
                    raise llm.Cancelled() from None

    return wait


@app.post("/api/documents")
def documents(body: DocumentsRequest):
    """What each shared file is: sales register, purchase register, bank statement or ledger, and why."""
    sheets, registers, _text, found = _shared_files(body.dataset_ids)
    _prefetch(sheets, registers)
    return found


def _books_company(company_id: int | None, sheets: list[dict]) -> int | None:
    """The company whose books the chat may add a shared sheet to: one that exists, and only when files are shared.
    A company deleted meanwhile is not an error: the chat still answers, without that tool."""
    if company_id is None or not sheets:
        return None
    try:
        accounts_service.get_company(company_id)
    except accounts_service.AccountsError:
        return None
    return company_id


def _pending_registers(found: list[dict], company_id: int | None, messages: list[dict]) -> list[dict]:
    """Shared sheets that are (or may be) a sales or purchase register and are not in the company's books yet (nor
    imported as a register already, whatever that import posted), while the person's latest message does not say which
    register: the answer asks, and the app shows a button for each register. Only with a company. The suggestion is the
    detected register when it is fairly sure and nothing points the other way."""
    previous = messages[-2]["content"] if len(messages) > 1 and messages[-2]["role"] == "assistant" else ""
    if company_id is None or says_register(messages[-1]["content"], llm.strip_context(previous)):
        return []
    candidates = [f for f in found if f["kind"] in books.REGISTERS]
    tables = [f["table_name"] for f in candidates]
    in_books = accounts_imports.imported_tables(company_id, tables) | accounts_imports.answered_tables(company_id, tables)
    return [{"dataset_id": f["dataset_id"], "table": f["table_name"], "filename": f["filename"], "sheet": f["sheet_name"],
             "suggestion": f["kind"] if f["confidence"] in _CONFIDENT and not f["against_register"] else None}
            for f in candidates if f["table_name"] not in in_books]


@app.post("/api/chat/stream")
def files_chat_stream(body: FilesChatRequest):
    sheets, registers, documents_text, found = _shared_files(body.dataset_ids)
    messages = _chat_messages(body)
    company_id = _books_company(body.company_id, sheets)
    pending = _pending_registers(found, company_id, messages)

    def answer(emit, cancel):
        if not registers:
            return llm.chat(body.provider, messages, sheets, emit=emit, fresh=body.fresh, documents=documents_text,
                            cancel=cancel, company_id=company_id, pending=pending)
        table, comparison = _register_jobs(registers)
        wait = _waiter(emit, cancel)
        stacked = wait(table)
        extra = {"registers": stacked} if stacked else {}
        # The app's exact comparison of the two registers, read only when the answer is not remembered.
        return llm.chat(body.provider, messages, sheets, extra, emit=emit, fresh=body.fresh, documents=documents_text,
                        combined=(lambda: wait(comparison)) if stacked else None, cancel=cancel, company_id=company_id,
                        pending=pending)

    return _stream_chat(answer)


@app.post("/api/datasets/{dataset_id}/chat/stream")
def chat_stream(dataset_id: int, body: ChatRequest):
    sheets, messages = _dataset_or_404(dataset_id)["sheets"], _chat_messages(body)
    return _stream_chat(lambda emit, cancel: llm.chat(body.provider, messages, sheets, emit=emit, fresh=body.fresh,
                                                      cancel=cancel))


@app.post("/api/datasets/{dataset_id}/chat", response_model=ChatResponse)
def chat(dataset_id: int, body: ChatRequest):
    dataset = _dataset_or_404(dataset_id)
    try:
        return llm.chat(body.provider, _chat_messages(body), dataset["sheets"])
    except llm.LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# --- Books: sales and purchase registers together ----------------------------------------------


def _book_or_404(book_id: int) -> dict:
    book = database.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Books not found.")
    return book


def _book_detail(book: dict) -> dict:
    return {
        **{k: book[k] for k in ("id", "name", "created_at")},
        "sheets": [
            {**{k: s[k] for k in ("dataset_id", "filename", "sheet_name", "table_name", "row_count")},
             "register_type": s["register"], "mapping": reports.effective_mapping(s["profile"])}
            for s in book["sheets"]
        ],
        "reports": books.KINDS,
    }


@app.get("/api/books", response_model=list[BookSummary])
def list_books():
    return database.list_books()


@app.post("/api/books", response_model=BookDetail, status_code=201)
def create_book(body: CreateBookRequest):
    registers: dict[str, str] = {}  # table name -> register; a sheet is linked once even if its upload is listed twice
    for ids, register in ((body.sales, "sales"), (body.purchases, "purchases"), (body.mixed, None)):
        for dataset_id in ids:
            dataset = _dataset_or_404(dataset_id)
            for sheet in dataset["sheets"]:
                guessed = register or books.guess_register(sheet["sheet_name"], dataset["filename"]) or "unused"
                registers.setdefault(sheet["table_name"], guessed)
    for table_name, register in body.registers.items():
        if table_name not in registers:
            _sheet_by_table_or_422(table_name)
        registers[table_name] = register
    if "sales" not in registers.values() or "purchases" not in registers.values():
        raise HTTPException(status_code=422, detail=(
            "A set needs at least one sales register and one purchase register. Choose a sales file and a purchases "
            "file, or mark which sheet is sales and which is purchases."))
    return _book_detail(_book_or_404(database.create_book(body.name.strip(), list(registers.items()))))


def _sheet_by_table_or_422(table_name: str) -> dict:
    """A sheet named in a request by its table name alone (table names are ds<upload id>_<sheet>)."""
    head, _, _rest = table_name.partition("_")
    dataset = database.get_dataset(int(head[2:])) if head.startswith("ds") and head[2:].isdigit() else None
    sheet = next((s for s in (dataset or {}).get("sheets", []) if s["table_name"] == table_name), None)
    if sheet is None:
        raise HTTPException(status_code=422, detail=f'Sheet "{table_name}" was not found. Its upload may have been '
                                                    "deleted; upload the file again and choose its sheets.")
    return sheet


@app.get("/api/books/{book_id}", response_model=BookDetail)
def get_book(book_id: int):
    return _book_detail(_book_or_404(book_id))


@app.put("/api/books/{book_id}/sheets", response_model=BookDetail)
def set_book_sheets(book_id: int, body: BookRegistersRequest):
    _book_or_404(book_id)
    database.set_book_registers(book_id, body.registers)
    return _book_detail(_book_or_404(book_id))


@app.delete("/api/books/{book_id}", status_code=204)
def delete_book(book_id: int):
    if not database.delete_book(book_id):
        raise HTTPException(status_code=404, detail="Books not found.")
    _delete_chats(f"book-{book_id}")


@app.get("/api/books/{book_id}/reports/{kind}", response_model=Report)
def book_report(
    book_id: int,
    kind: str,
    party: str | None = None,
    as_of: date | None = None,
    opening_stock: float = 0.0,
    closing_stock: float | None = None,
    measure: str | None = None,
):
    if kind not in books.KINDS:
        raise HTTPException(status_code=404, detail="Unknown report.")
    try:
        return books.build(kind, _book_or_404(book_id), party=party, as_of=as_of,
                           opening_stock=opening_stock, closing_stock=closing_stock, measure=measure)
    except books.BookError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _book_tables(book: dict) -> tuple[list[dict], dict]:
    """The set's register sheets, plus both registers stacked as one "registers" table when they can be read."""
    sheets = [s for s in book["sheets"] if s["register"] in books.REGISTERS]
    combined = analysis.register_table(sheets)
    return sheets, ({"registers": combined} if combined else {})


@app.post("/api/books/{book_id}/sql", response_model=QueryOut)
def book_sql(book_id: int, body: SqlRequest):
    sheets, extra = _book_tables(_book_or_404(book_id))
    return _sql(sheets, body.sql, extra)


@app.post("/api/books/{book_id}/analyse")
def analyse_book(book_id: int, body: AnalysisRequest):
    sheets, extra = _book_tables(_book_or_404(book_id))
    return _analyse(sheets, body, extra)


@app.get("/api/books/{book_id}/fields")
def book_fields(book_id: int):
    sheets, extra = _book_tables(_book_or_404(book_id))
    return _fields(sheets, extra, {"registers": "Sales and purchases together"})


@app.post("/api/books/{book_id}/chat/stream")
def book_chat_stream(book_id: int, body: ChatRequest):
    sheets, extra = _book_tables(_book_or_404(book_id))
    if not sheets:
        raise HTTPException(status_code=422, detail="This set has no sales or purchase sheets.")
    messages = _chat_messages(body)
    return _stream_chat(lambda emit, cancel: llm.chat(body.provider, messages, sheets, extra, emit=emit, fresh=body.fresh,
                                                      cancel=cancel))


@app.post("/api/books/{book_id}/chat", response_model=ChatResponse)
def book_chat(book_id: int, body: ChatRequest):
    sheets, extra = _book_tables(_book_or_404(book_id))
    if not sheets:
        raise HTTPException(status_code=422, detail="This set has no sales or purchase sheets.")
    try:
        return llm.chat(body.provider, _chat_messages(body), sheets, extra)
    except llm.LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.post("/api/chat/followups", response_model=Followups)
def chat_followups(body: FollowupsRequest):
    """Up to three short questions the person may ask next (the chips under an answer), about the same data as the
    chat: the set's registers (book_id), else the shared files (dataset_ids), else none. Empty when the model fails."""
    if body.book_id is not None:
        sheets, extra = _book_tables(_book_or_404(body.book_id))
    else:
        sheets, extra = _shared_files(body.dataset_ids)[0], None
    # Any length, as for the chat. Older turns are dropped, though more are kept than for an answer: the earlier
    # questions are listed to the model so that none is suggested again.
    messages = [m.model_dump() for m in body.messages][-2 * MAX_CHAT_MESSAGES:]
    return {"suggestions": followups.suggest(messages, sheets, extra, body.provider)}


# --- Chat history, kept here so that every device shows the same conversations ----------------

MAX_CHAT_BYTES = 2 * 1024 * 1024
MAX_CHAT_BODY = MAX_CHAT_BYTES + MAX_CHAT_BYTES // 4  # a body this large is refused before it is parsed
CHAT_TOO_LARGE = "This conversation is larger than 2 MB; start a new chat to go on."
# Conversations kept per scope (the app keeps 30): older ones become deletions at their own time, so the history a
# device reads stays bounded.
MAX_CHATS_PER_SCOPE = 100
_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _delete_chats(scope: str) -> None:
    """The upload or set of this scope was deleted: so are its conversations, on every device and in MongoDB."""
    for chat_id in database.delete_scope_chats(scope):
        mongo_sync.touch("chat", f"{scope}/{chat_id}")


@app.get("/api/chats", response_model=ChatList)
def list_chats(scope: str = Query(pattern=CHAT_SCOPE, max_length=40)):
    """The scope's conversations, newest first, and those deleted on any device (a device that still has one drops it)."""
    chats, deleted = database.list_chats(scope, MAX_CHATS_PER_SCOPE)
    return {"chats": chats, "deleted": deleted}


@app.put("/api/chats/{scope}/{chat_id}", response_model=ChatSaved)
def save_chat(body: Conversation, scope: str = PathParam(pattern=CHAT_SCOPE, max_length=40),
              chat_id: str = PathParam(pattern=CHAT_ID)):
    """Keep the newer copy: the body when its "updated" is larger than that of the server's copy or deletion (equal: the
    server's). Returns the copy kept, so a device holding an older one replaces it."""
    if body.id != chat_id:
        raise HTTPException(status_code=422, detail="The conversation's id does not match the address.")
    try:
        data = json.dumps(body.model_dump(), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except ValueError as exc:  # NaN or Infinity, which JSON (and so the app) cannot read back
        raise HTTPException(status_code=422, detail="The conversation holds a number that is not finite.") from exc
    # Half of a surrogate pair (a title cut in the middle of an emoji) cannot be stored as UTF-8 here or in MongoDB: it
    # becomes U+FFFD. A whole pair is already one character.
    data = _LONE_SURROGATE.sub("\ufffd", data)
    # The app measures 2 MB on its own JSON; written again here a number can grow (1e-7 becomes 1e-07), so the limit
    # here is the body's.
    if len(data.encode()) > MAX_CHAT_BODY:
        raise HTTPException(status_code=413, detail=CHAT_TOO_LARGE)
    if not database.chat_scope_exists(scope):
        # The upload or set was deleted (a device that did not know yet kept answering in it): the conversation goes
        # too, so the device drops it. Nothing is stored for a scope that does not exist. Not a 404, which the app
        # reads as a server without these routes.
        return {"chat": None, "deleted": {"id": chat_id, "updated": max(int(time.time() * 1000), body.updated)}}
    kept = database.save_chat(scope, chat_id, body.updated, data)
    mongo_sync.touch("chat", f"{scope}/{chat_id}")
    for old, updated in database.trim_chats(scope, MAX_CHATS_PER_SCOPE):
        mongo_sync.touch("chat", f"{scope}/{old}")
        if old == chat_id:  # older than every conversation kept
            kept = {"chat": None, "deleted": {"id": old, "updated": updated}}
    return kept


@app.delete("/api/chats/{scope}/{chat_id}", status_code=204)
def delete_chat(scope: str = PathParam(pattern=CHAT_SCOPE, max_length=40), chat_id: str = PathParam(pattern=CHAT_ID),
                updated: float | None = Query(None, ge=0, le=2**53 - 1, allow_inf_nan=False)):
    """Delete a conversation on every device: a tombstone at ``updated`` (ms since 1970; default now), unless the
    server's copy is newer."""
    database.delete_chat(scope, chat_id, int(time.time() * 1000) if updated is None else chat_time(updated))
    mongo_sync.touch("chat", f"{scope}/{chat_id}")
