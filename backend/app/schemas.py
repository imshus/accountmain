"""Request and response models for the HTTP API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ProviderId = Literal["openai", "anthropic"]


class ProviderStatus(BaseModel):
    id: ProviderId
    label: str
    model: str
    configured: bool
    key_name: str


class Health(BaseModel):
    status: str
    providers: list[ProviderStatus]
    default_provider: ProviderId


class DatasetSummary(BaseModel):
    id: int
    filename: str
    size_bytes: int
    uploaded_at: datetime
    sheet_count: int
    row_count: int


class Preview(BaseModel):
    columns: list[str]
    rows: list[list[Any]]


class SheetDetail(BaseModel):
    sheet_name: str
    table_name: str
    row_count: int
    profile: dict[str, Any]
    preview: Preview


class DatasetDetail(BaseModel):
    id: int
    filename: str
    size_bytes: int
    uploaded_at: datetime
    sheets: list[SheetDetail]


class ColumnCalcResult(BaseModel):
    expression: str
    stats: "ColumnCalcStats"
    preview: Preview
    saved_column: str | None = None
    sheet: SheetDetail | None = None  # the updated sheet when the result was saved as a column
    check: dict[str, Any] | None = None  # formula check result when compare_to was given


class CalcRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=2000)


class CalcResult(BaseModel):
    expression: str
    result: str


class RowsPage(BaseModel):
    columns: list[str]  # the first column is "_rowid", used to delete an entry
    rows: list[list[Any]]
    total: int
    offset: int


class AddRowRequest(BaseModel):
    values: dict[str, str | float | None]


class ColumnCalcRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=2000)
    save_as: str | None = Field(default=None, max_length=80)
    # Optional: test the formula against an existing column ("does Fine = Net.Wt × Tunch / 100 on every row?").
    compare_to: str | None = None
    tolerance: float = Field(default=0.005, ge=0)


class ColumnCalcStats(BaseModel):
    count: int
    sum: float
    mean: float | None
    min: float | None
    max: float | None


class NotesRequest(BaseModel):
    notes: str = Field(max_length=5000)


class SetupRequest(BaseModel):
    # role -> column name ("" clears a role). None leaves the saved value unchanged.
    mapping: dict[str, str] | None = None
    # account name -> group (e.g. "Indirect Expenses"); "" clears an override.
    classification: dict[str, str] | None = None


class SetupOut(BaseModel):
    roles: dict[str, str]
    mapping: dict[str, str]
    detected: dict[str, str]
    classification: dict[str, str]
    groups: list[str]
    reports: dict[str, str]


class Report(BaseModel):
    title: str
    mapping: dict[str, str]
    cards: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    checks: list[dict[str, Any]]
    options: dict[str, Any]


RegisterName = Literal["sales", "purchases", "unused"]


class CreateBookRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sales: list[int] = []  # upload ids whose sheets are sales registers
    purchases: list[int] = []  # upload ids whose sheets are purchase registers
    mixed: list[int] = []  # uploads holding both; each sheet is classified from its name
    # Table name -> register, for sheets whose names do not say (one workbook with Sheet1 / Sheet2). It wins over
    # the lists above; an upload reached only through it adds just the sheets named here.
    registers: dict[str, RegisterName] = {}


class BookRegistersRequest(BaseModel):
    registers: dict[str, RegisterName]  # table name -> register


class BookSummary(BaseModel):
    id: int
    name: str
    created_at: datetime
    sales_sheets: int
    purchase_sheets: int


class BookSheet(BaseModel):
    dataset_id: int
    filename: str
    sheet_name: str
    table_name: str
    row_count: int
    register_type: RegisterName  # "register" would shadow a BaseModel attribute
    mapping: dict[str, str]


class BookDetail(BaseModel):
    id: int
    name: str
    created_at: datetime
    sheets: list[BookSheet]
    reports: dict[str, str]


class GstNetOut(BaseModel):
    output_tax: dict[str, float]
    input_credit: dict[str, float]
    cash_payable: dict[str, float]
    credit_carried_forward: dict[str, float]
    total_cash_payable: float
    steps: list[str]


class MeasureIn(BaseModel):
    agg: Literal["sum", "count", "average", "min", "max", "distinct"]
    column: str = ""


class GroupIn(BaseModel):
    column: str
    bucket: Literal["none", "day", "month", "quarter", "fy", "year"] = "none"


class FilterIn(BaseModel):
    column: str
    op: Literal["=", "!=", ">", ">=", "<", "<=", "between", "contains", "in", "blank", "not_blank"]
    value: str = ""
    value2: str = ""
    values: list[str] = []


class AnalysisRequest(BaseModel):
    table: str = ""
    measures: list[MeasureIn] = Field(min_length=1, max_length=4)
    group_by: list[GroupIn] = Field(default=[], max_length=2)
    filters: list[FilterIn] = Field(default=[], max_length=8)
    sort: Literal["value_desc", "value_asc", "label"] | None = None
    limit: int = Field(default=0, ge=0, le=500)
    across: bool = False


class SqlRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=20_000)


class QueryOut(BaseModel):
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int = 0
    truncated: bool = False
    elapsed_ms: float | None = None
    error: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    # The whole conversation so far, oldest first, ending with the user's new message.
    messages: list[ChatMessage] = Field(min_length=1)
    provider: ProviderId | None = None
    # Regenerate: write a new answer even if this question was answered before on the same data.
    fresh: bool = False


class FilesChatRequest(ChatRequest):
    """A chat over files shared in the conversation (the main chat screen)."""
    dataset_ids: list[int] = Field(default=[], max_length=10)  # none yet: general accounting questions


class DocumentsRequest(BaseModel):
    dataset_ids: list[int] = Field(min_length=1, max_length=10)


class CalculationOut(BaseModel):
    expression: str
    result: str | None
    error: str | None = None


class Verification(BaseModel):
    # "verified": every figure matched a tool result; "unverified": some did not; "no_figures": nothing to check.
    status: Literal["verified", "unverified", "no_figures"]
    figures: int
    unverified: list[str]
    corrected: bool


class ChatResponse(BaseModel):
    answer: str
    queries: list[QueryOut]
    calculations: list[CalculationOut]
    formula_checks: list[dict[str, Any]]
    analyses: list[dict[str, Any]] = []
    verification: Verification
    model: str
    provider: ProviderId
    cached: bool = False
