// Shapes returned by the FastAPI backend (see backend/app/schemas.py and analytics.py).

export type ProviderId = "openai" | "anthropic";

export type ProviderStatus = {
  id: ProviderId;
  label: string;
  model: string;
  configured: boolean;
  key_name: string;
};

export type Health = {
  status: string;
  providers: ProviderStatus[];
  default_provider: ProviderId;
};

export type DatasetSummary = {
  id: number;
  filename: string;
  size_bytes: number;
  uploaded_at: string;
  sheet_count: number;
  row_count: number;
};

export type ColumnKind = "number" | "date" | "text";
export type ValueFormat = "money" | "number" | "count" | "percent" | "text";

export type ColumnProfile = {
  name: string;
  label: string;
  kind: ColumnKind;
  non_null: number;
  nulls: number;
  unique: number;
  role: "identifier" | null;
  stats:
    | {
        sum: number;
        mean: number;
        median: number;
        std: number;
        min: number;
        max: number;
        p25: number;
        p75: number;
        negatives: number;
        zeros: number;
      }
    | { min: string; max: string; span_days: number }
    | { top: { value: string; count: number }[] }
    | null;
};

export type TotalCard = {
  label: string;
  value: number;
  format: ValueFormat;
  hint?: string | null;
};

export type TableColumn = { key: string; label: string; format: ValueFormat };
export type SummaryTable = {
  columns: TableColumn[];
  rows: Record<string, string | number>[];
};

export type SheetSummary = {
  detected: {
    date: string | null;
    amount: string | null;
    debit: string | null;
    credit: string | null;
    category: string | null;
    tax: string[];
  };
  period: { from: string; to: string } | null;
  totals: TotalCard[];
  monthly: SummaryTable | null;
  by_category: (SummaryTable & { category_column: string; groups: number }) | null;
};

export type Check = {
  level: "ok" | "info" | "warning";
  message: string;
  edit?: boolean;
};

export type SheetProfile = {
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
  summary: SheetSummary;
  checks: Check[];
  user_notes?: string | null;
  calculated_columns?: string[];
};

export type Cell = string | number | boolean | null;

export type Sheet = {
  sheet_name: string;
  table_name: string;
  row_count: number;
  profile: SheetProfile;
  preview: { columns: string[]; rows: Cell[][] };
};

export type DatasetDetail = Omit<DatasetSummary, "sheet_count" | "row_count"> & {
  sheets: Sheet[];
};

export type QueryResult = {
  sql: string | null;
  columns: string[];
  rows: Cell[][];
  row_count: number;
  truncated: boolean;
  elapsed_ms: number | null;
  error: string | null;
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type FormulaCheck = {
  table?: string;
  target: string;
  expression: string;
  tolerance?: number;
  rows_checked?: number;
  rows_blank?: number;
  matches?: number;
  mismatches?: number;
  max_difference?: number | null;
  examples?: { row: number; actual: number; expected: number; difference: number }[];
  error: string | null;
};

/** Live progress while the AI answers (server-sent events). */
export type ChatEvent =
  | { type: "step"; text: string }
  | { type: "delta"; text: string }
  | { type: "reset"; text?: string }
  | { type: "analysis"; result: AnalysisResult }
  | { type: "done"; result: ChatResult }
  | { type: "error"; status: number; message: string };

export type ChatResult = {
  answer: string;
  queries: QueryResult[];
  calculations: { expression: string; result: string | null; error: string | null }[];
  formula_checks: FormulaCheck[];
  analyses?: AnalysisResult[];
  verification: {
    status: "verified" | "unverified" | "no_figures";
    figures: number;
    unverified: string[];
    corrected: boolean;
  };
  model: string;
  provider: ProviderId;
  /** Same question on unchanged data: answered from memory, instantly. */
  cached?: boolean;
  /** Shared sheets the AI added to the company's books (home chat with a company_id); absent from older servers. */
  imports?: ChatImport[];
  /** Shared sheets that look like (or might be) a sales or purchase register and are not in the books yet: the answer
   * ends by asking which register they are (home chat with a company_id); absent from older servers. */
  pending_registers?: PendingRegister[];
};

/** A shared sheet the AI asks about; `suggestion` is the register its data points to, null when it cannot tell. */
export type PendingRegister = {
  dataset_id: number;
  table: string;
  filename: string;
  sheet: string;
  suggestion: "sales" | "purchases" | null;
};

/** One shared sheet added to the books as a sales or purchase register; rows already in the books are skipped. */
export type ChatImport = {
  register: "sales" | "purchases";
  dataset_id: number;
  table: string;
  filename: string;
  sheet: string;
  created: number;
  skipped: number;
  problems: string[];
};

/** Suggested next questions after an answer: about a book's sheets (book_id), else the files in dataset_ids. */
export type FollowupsRequest = { messages: ChatMessage[]; dataset_ids: number[]; book_id: number | null; provider: ProviderId | null };
/** 0 to 3 short questions; empty when the model could not suggest any. */
export type FollowupsResponse = { suggestions: string[] };

export type RowsPage = { columns: string[]; rows: Cell[][]; total: number; offset: number };

export type ColumnCalcResult = {
  expression: string;
  stats: { count: number; sum: number; mean: number | null; min: number | null; max: number | null };
  preview: { columns: string[]; rows: Cell[][] };
  saved_column: string | null;
  sheet: Sheet | null;
  check: FormulaCheck | null;
};

export type ReportFormat = ValueFormat | "drcr" | "date" | "group" | "weight" | "weight_drcr" | "carat";
export type ReportTable = {
  title: string | null;
  columns: { key: string; label: string; format: ReportFormat }[];
  rows: Record<string, Cell | undefined>[];
  total: Record<string, Cell> | null;
};
export type Report = {
  title: string;
  mapping: Record<string, string>;
  cards: { label: string; value: number; format: ReportFormat; hint?: string | null }[];
  tables: ReportTable[];
  checks: Check[];
  options: {
    accounts?: string[];
    groups?: string[];
    parties?: string[];
    measures?: { name: string; label: string }[];
    ledgers?: { id: number; name: string; group: string }[];
    voucher_types?: string[];
    metals?: Metal[];
  };
};

export type Setup = {
  roles: Record<string, string>;
  mapping: Record<string, string>;
  detected: Record<string, string>;
  classification: Record<string, string>;
  groups: string[];
  reports: Record<string, string>;
};

export type RegisterType = "sales" | "purchases" | "unused";

export type BookSummary = {
  id: number;
  name: string;
  created_at: string;
  sales_sheets: number;
  purchase_sheets: number;
};

export type BookSheet = {
  dataset_id: number;
  filename: string;
  sheet_name: string;
  table_name: string;
  row_count: number;
  register_type: RegisterType;
  mapping: Record<string, string>;
};

export type BookDetail = {
  id: number;
  name: string;
  created_at: string;
  sheets: BookSheet[];
  reports: Record<string, string>;
};

// --- Double-entry books ------------------------------------------------------------------------

export type VoucherType =
  | "Sales"
  | "Purchase"
  | "Receipt"
  | "Payment"
  | "Contra"
  | "Journal"
  | "Credit Note"
  | "Debit Note"
  | "Metal Receipt"
  | "Metal Issue";

export type Metal = "gold" | "silver";

export type Company = {
  id: number;
  name: string;
  gstin: string | null;
  state_code: string | null;
  fy_start: string;
  locked_until: string | null;
  created_at: string;
  voucher_count?: number;
};

export type Ledger = {
  id: number;
  name: string;
  group_name: string;
  opening_paise: number;
  /** Balance to date; for income and expense ledgers only the latest financial year (from closing_from). */
  closing_paise: number;
  /** Start of the year an income or expense ledger's closing covers; null for balance-sheet ledgers. */
  closing_from?: string | null;
  /** An income or expense ledger's movement in earlier years, carried to Capital as "Profit & Loss A/c" (+ = Dr). */
  earlier_years_paise?: number;
  tax_kind: string | null;
  gstin: string | null;
  state_code: string | null;
  credit_days: number | null;
  /** Fine metal in milligrams (+ = Dr: owes us / in hand), only for ledgers that have any. */
  metal?: Partial<Record<Metal, { opening_mg: number; closing_mg: number }>>;
};

export type AccountsMeta = {
  groups: { name: string; parent: string | null; nature: string }[];
  voucher_types: VoucherType[];
  metals: Metal[];
  /** GST state codes ("27") and names, for a ledger's place of supply. */
  states: { code: string; name: string }[];
};

export type VoucherRow = {
  id: number;
  vtype: VoucherType;
  number: string;
  date: string;
  narration: string | null;
  reference: string | null;
  cancelled: boolean;
  source: string | null;
  amount: number; // paise
  fine_mg: number;
  ledgers: string[];
  /** Up to 3 item names of the bill, in line order (absent from older servers). */
  items?: string[];
  /** The bill's total net weight in milligrams; null when no line has a weight (absent from older servers). */
  net_mg?: number | null;
};

export type MetalLineDetail = {
  id: number;
  ledger_id: number;
  ledger: string;
  metal: Metal;
  dr_mg: number;
  cr_mg: number;
  item: string | null;
  purity: string | null;
  tunch_bp: number | null;
  gross_mg: number | null;
  net_mg: number | null;
  dia_mct: number | null;
  stn_mct: number | null;
  pieces: number | null;
  tag_no: string | null;
};

export type VoucherDetail = Omit<VoucherRow, "amount" | "ledgers" | "fine_mg" | "items" | "net_mg"> & {
  metal_lines: MetalLineDetail[];
  lines: {
    id: number;
    ledger_id: number;
    ledger: string;
    dr_paise: number;
    cr_paise: number;
    bills: { kind: string; bill_ref: string | null; amount_paise: number; bill_date: string | null; due_date: string | null }[];
  }[];
  summary?: Record<string, number | boolean>;
};

export type ImportResult = { created: number; skipped: number; problems: string[]; notes: string[] };

export type GstNet = {
  output_tax: Record<string, number>;
  input_credit: Record<string, number>;
  cash_payable: Record<string, number>;
  credit_carried_forward: Record<string, number>;
  total_cash_payable: number;
  steps: string[];
};

/** What a shared file is, as the backend detected it from the data (with the evidence). */
export type DocumentInfo = {
  dataset_id: number;
  filename: string;
  sheet_name: string;
  table_name: string;
  rows: number;
  period: { from: string; to: string } | null;
  kind: "sales" | "purchases" | "bank" | "ledger" | "other";
  label: string;
  confidence: "high" | "medium" | "low";
  reasons: string[];
  against: string[];
  jewellery: boolean;
};

// --- Analyse (DuckDB + pandas on the backend) ----------------------------------------------------------

export type AnalysisField = { name: string; label: string; kind: "number" | "date" | "text"; scale: number | null };
export type AnalysisTable = { table: string; title: string; fields: AnalysisField[] };

export type Agg = "sum" | "count" | "average" | "min" | "max" | "distinct";
export type Bucket = "none" | "day" | "month" | "quarter" | "fy" | "year";
export type FilterOp = "=" | "!=" | ">" | ">=" | "<" | "<=" | "between" | "contains" | "in" | "blank" | "not_blank";

export type AnalysisSpec = {
  table: string;
  measures: { agg: Agg; column: string }[];
  group_by: { column: string; bucket: Bucket }[];
  filters: { column: string; op: FilterOp; value: string; value2: string; values: string[] }[];
  sort: "value_desc" | "value_asc" | "label" | null;
  limit: number;
  across: boolean;
};

export type AnalysisColumn = { key: string; label: string; format: "text" | "number" | "date"; decimals?: number };

export type AnalysisResult = {
  spec: AnalysisSpec;
  table_title: string;
  description: string;
  columns: AnalysisColumn[];
  rows: Record<string, string | number | null>[];
  total: Record<string, string | number | null> | null;
  groups: number;
  rows_matched: number;
  checks: Check[];
  elapsed_ms: number;
  error?: string | null;
};
