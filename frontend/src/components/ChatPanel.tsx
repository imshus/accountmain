import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiError, uploadFile, type StreamOptions } from "../api";
import { formatBytes, formatCount } from "../format";
import type {
  AnalysisResult,
  AnalysisSpec,
  ChatEvent,
  ChatMessage,
  ChatResult,
  DatasetDetail,
  DocumentInfo,
  FormulaCheck,
  Health,
  ProviderId,
  QueryResult,
  Sheet,
} from "../types";
import { AnalysisView } from "./AnalysePanel";
import DataTable from "./DataTable";

type TableRef = { table_name: string; sheet_name: string };

export type ChatStream = (
  messages: ChatMessage[],
  provider: ProviderId,
  onEvent: (event: ChatEvent) => void,
  options: StreamOptions & { datasetIds?: number[] },
) => Promise<ChatResult>;

type Props = {
  /** Where this chat's conversations are kept on this device, e.g. "home" or "ds-2". */
  scope: string;
  /** What the chat is about: a file name, a sales + purchases set, or "your files". */
  subject: string;
  suggestionList: string[];
  health: Health | null;
  stream: ChatStream;
  /** Advanced SQL over the same tables (hidden behind a link). */
  tables?: TableRef[];
  defaultTable?: string;
  runSql?: (sql: string) => Promise<QueryResult>;
  /** Open one of the AI's analyses in the Analyse screen. */
  onOpenAnalysis?: (spec: AnalysisSpec) => void;
  /** The home screen: the chat fills the whole window, like ChatGPT. */
  page?: boolean;
  /** Opens the uploaded files and company books (from the + menu). */
  onLibrary?: () => void;
  /** The main chat: Excel files can be attached; they are uploaded and become the conversation's data. */
  attachments?: {
    onUploaded: (dataset: DatasetDetail) => void;
    /** Build a sales + purchases set from the conversation's sheets (each sheet keeps the register it was detected as). */
    onCompare: (documents: DocumentInfo[], name: string) => Promise<void>;
  };
};

type SharedFile = { name: string; size: number; datasetId?: number; kinds?: string[] };

type Turn = {
  id: number;
  question: string;
  /** What the person typed is shown; this is what was sent (e.g. "Explain the files I just shared."). */
  prompt?: string;
  files?: SharedFile[];
  result?: ChatResult;
  error?: string;
  stopped?: boolean;
  /** Text written before the person pressed stop. */
  partial?: string;
  /** While the answer streams in: what the AI has done so far and the text written so far. */
  live?: { steps: string[]; text: string; note?: string; analysis?: AnalysisResult };
};

type Conversation = { id: string; title: string; updated: number; datasetIds: number[]; documents: DocumentInfo[]; turns: Turn[] };

const ACCEPTED = [".xlsx", ".xlsm", ".xls", ".csv"];
const MAX_CHATS = 30;
const MAX_TURNS = 40;
const MAX_ROWS = 50;
/** Characters of JSON kept per scope; every scope shares the browser's ~5M-character quota. */
const STORE_BUDGET = 1_500_000;
const REMARK_PLUGINS = [remarkGfm];
const CONNECTING = "Connecting to the server…";
const NOT_SAVED = "This chat could not be saved on this device (storage is full or blocked).";

/** Starter questions based on the columns the backend recognised in the sheet. */
export function suggestions(sheet: Sheet): string[] {
  const { detected } = sheet.profile.summary;
  const label = (name: string | null) =>
    sheet.profile.columns.find((c) => c.name === name)?.label.toLowerCase() ?? name ?? "";
  const measure = detected.amount ?? detected.credit;
  const out: string[] = [];
  if (detected.debit && detected.credit && detected.date) {
    out.push(`What are total ${label(detected.debit)} and ${label(detected.credit)} for each month?`);
  }
  if (detected.category && measure) {
    out.push(`Which ${label(detected.category)} has the highest ${label(measure)}?`);
  }
  if (detected.amount) out.push(`Show the 5 largest entries by ${label(detected.amount)}.`);
  if (detected.tax.length && detected.date) out.push(`How much ${label(detected.tax[0])} is there each month?`);
  out.push("Summarise this data in a few bullet points.");
  out.push("Which formulas link the number columns? Check them on every row.");
  return out.slice(0, 4);
}

// --- conversations kept on this device -------------------------------------------------------------

const STORE_PREFIX = "accountsai.chats.";
/** The JSON last written per key, so an unchanged list is not written again. */
const lastSaved = new Map<string, string>();

function storeKey(scope: string): string {
  return `${STORE_PREFIX}${scope}`;
}

const NO_CHECK: ChatResult["verification"] = { status: "no_figures", figures: 0, unverified: [], corrected: false };

const list = <T,>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : []);

/** A stored answer made safe to show: a failed analysis has no rows, and older records may lack fields. */
function cleanResult(result: ChatResult, rows: number): ChatResult {
  const check = result.verification && typeof result.verification === "object" ? result.verification : NO_CHECK;
  return {
    ...result,
    answer: typeof result.answer === "string" ? result.answer : "",
    queries: list<QueryResult>(result.queries).map((q) => ({ ...q, columns: list(q.columns), rows: list<QueryResult["rows"][number]>(q.rows).slice(0, rows) })),
    analyses: list<AnalysisResult>(result.analyses).map((a) => ({ ...a, columns: list(a.columns), rows: list<AnalysisResult["rows"][number]>(a.rows).slice(0, rows) })),
    calculations: list(result.calculations),
    formula_checks: list(result.formula_checks),
    verification: { ...NO_CHECK, ...check, unverified: list<string>(check.unverified) },
  };
}

/** Settled turns only (newest ``turns``), each query and analysis cut to ``rows`` rows. Throws on a malformed record. */
function slimChat(chat: Conversation, rows: number, turns: number): Conversation {
  if (!chat || typeof chat.id !== "string" || !Array.isArray(chat.turns)) throw new Error("malformed chat");
  return {
    id: chat.id,
    title: typeof chat.title === "string" ? chat.title : "",
    updated: Number(chat.updated) || 0,
    datasetIds: list<number>(chat.datasetIds).filter((id) => typeof id === "number"),
    documents: list<DocumentInfo>(chat.documents),
    turns: chat.turns
      .filter((t) => t && typeof t === "object" && (t.result || t.error || t.stopped))
      .slice(-Math.max(1, turns))
      .map(({ live: _live, ...t }) => ({
        ...t,
        question: typeof t.question === "string" ? t.question : "",
        files: list<SharedFile>(t.files),
        result: t.result ? cleanResult(t.result, rows) : undefined,
      })),
  };
}

/**
 * The chats as JSON within ``budget`` characters: query and analysis rows go first, then the oldest turns,
 * then the oldest chats. A record that cannot be serialised is skipped, so it never blocks the others.
 */
export function serializeChats(chats: Conversation[], budget = STORE_BUDGET): string {
  const pack = (rows: number, turns: number) => {
    const parts: { updated: number; json: string }[] = [];
    for (const chat of chats.slice(0, MAX_CHATS)) {
      try {
        const slim = slimChat(chat, rows, turns);
        if (slim.turns.length) parts.push({ updated: slim.updated, json: JSON.stringify(slim) });
      } catch {
        // A malformed record is dropped; the rest are still kept.
      }
    }
    return parts;
  };
  const size = (parts: { json: string }[]) => parts.reduce((n, p) => n + p.json.length + 1, 1);
  let parts = pack(MAX_ROWS, MAX_TURNS);
  for (const turns of [MAX_TURNS, 20, 10, 5, 2, 1]) {
    if (size(parts) <= budget) break;
    parts = pack(0, turns);
  }
  while (parts.length && size(parts) > budget) {
    let oldest = 0;
    parts.forEach((p, i) => {
      if (p.updated < parts[oldest].updated) oldest = i;
    });
    parts.splice(oldest, 1);
  }
  return `[${parts.map((p) => p.json).join(",")}]`;
}

function loadChats(scope: string): Conversation[] {
  let stored: unknown;
  try {
    stored = JSON.parse(localStorage.getItem(storeKey(scope)) ?? "[]");
  } catch {
    return [];
  }
  const out: Conversation[] = [];
  for (const raw of list<Conversation>(stored)) {
    try {
      // Conversations saved before files could be shared have no datasetIds / documents yet.
      out.push(slimChat(raw, Infinity, Infinity));
    } catch {
      // Skip a malformed record.
    }
  }
  return out;
}

/** False when nothing could be written (quota reached or storage blocked), even after shrinking the history. */
function saveChats(scope: string, chats: Conversation[]): boolean {
  const key = storeKey(scope);
  for (const budget of [STORE_BUDGET, STORE_BUDGET / 4, STORE_BUDGET / 16]) {
    let json: string;
    try {
      json = serializeChats(chats, budget);
    } catch {
      return false;
    }
    if (lastSaved.get(key) === json) return true;
    try {
      localStorage.setItem(key, json);
      lastSaved.set(key, json);
      return true;
    } catch {
      // Usually the quota: try again with a smaller history.
    }
  }
  return false;
}

function chatScopes(): string[] {
  try {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(STORE_PREFIX)) keys.push(key.slice(STORE_PREFIX.length));
    }
    return keys;
  } catch {
    return [];
  }
}

/** Remove the conversations kept for one scope, e.g. "ds-4" or "book-2" after it is deleted. */
export function forgetChats(scope: string): void {
  lastSaved.delete(storeKey(scope));
  try {
    localStorage.removeItem(storeKey(scope));
  } catch {
    // Storage blocked: nothing was kept anyway.
  }
}

/** A deleted upload: drop its chat and take it out of every conversation that shared it. */
export function forgetDataset(id: number): void {
  forgetChats(`ds-${id}`);
  for (const scope of chatScopes()) {
    const chats = loadChats(scope);
    if (!chats.some((c) => c.datasetIds.includes(id) || c.documents.some((d) => d.dataset_id === id))) continue;
    saveChats(
      scope,
      chats.map((c) => ({ ...c, datasetIds: c.datasetIds.filter((x) => x !== id), documents: c.documents.filter((d) => d.dataset_id !== id) })),
    );
  }
}

/** Start-up: remove the chats of uploads and sets that no longer exist. */
export function sweepChats(datasetIds: number[], bookIds: number[]): void {
  const datasets = new Set(datasetIds);
  const books = new Set(bookIds);
  for (const scope of chatScopes()) {
    const match = /^(ds|book)-(\d+)$/.exec(scope);
    if (match && !(match[1] === "ds" ? datasets : books).has(Number(match[2]))) forgetChats(scope);
  }
}

/** Earlier answered turns as plain messages, so follow-up questions keep their context. */
function history(turns: Turn[]): ChatMessage[] {
  return turns.flatMap((turn) =>
    turn.result
      ? [
          { role: "user" as const, content: turn.prompt ?? turn.question },
          { role: "assistant" as const, content: turn.result.answer },
        ]
      : [],
  );
}

function defaultSql(table: string): string {
  return `SELECT *\nFROM "${table}"\nLIMIT 20`;
}

/** Give the turn's file cards the dataset ids of the files that uploaded (matched by name and size). */
function linkCards(cards: SharedFile[] | undefined, done: { file: File; detail: DatasetDetail }[]): SharedFile[] {
  const left = [...done];
  return (cards ?? []).map((card) => {
    if (card.datasetId !== undefined) return card;
    const i = left.findIndex((d) => d.file.name === card.name && d.file.size === card.size);
    if (i < 0) return card;
    const [hit] = left.splice(i, 1);
    return { ...card, datasetId: hit.detail.id };
  });
}

/** What a screen reader hears when an answer is ready. */
function readyText(result: ChatResult): string {
  const check = result.verification;
  if (check.status === "verified") return `Answer ready. ${check.figures} figure${check.figures === 1 ? "" : "s"} checked against your data.`;
  if (check.status === "unverified") return `Answer ready. Check ${check.unverified.join(", ")}.`;
  return "Answer ready.";
}

// --- small pieces ----------------------------------------------------------------------------------

const Icon = {
  send: (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  ),
  stop: (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" rx="2" />
    </svg>
  ),
  plus: (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),
  edit: (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
    </svg>
  ),
  menu: (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h10" />
    </svg>
  ),
  copy: (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V6a2 2 0 012-2h9" />
    </svg>
  ),
  again: (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 11a8 8 0 10-2.3 5.7M20 4v7h-7" />
    </svg>
  ),
  file: (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" />
      <path d="M14 3v5h5M8.5 13h7M8.5 16.5h7" />
    </svg>
  ),
  sidebar: (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9.5 4v16" />
    </svg>
  ),
  search: (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="M20 20l-4.2-4.2" />
    </svg>
  ),
  clip: (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20.5 11.5l-8.4 8.4a5 5 0 01-7.1-7.1l8.4-8.4a3.4 3.4 0 014.8 4.8l-8.4 8.4a1.7 1.7 0 01-2.4-2.4l7.7-7.7" />
    </svg>
  ),
  folder: (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 7a2 2 0 012-2h4l2 2.5h8a2 2 0 012 2V17a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  ),
};

const NARROW = "(max-width: 860px)";
const SIDEBAR_KEY = "accountsai.sidebar";

function AnalysisDetails({ analysis, onOpen }: { analysis: AnalysisResult; onOpen?: (spec: AnalysisSpec) => void }) {
  return (
    <details className="query">
      <summary>
        Analysis{analysis.error ? <span className="pill danger small-pill">error</span> : <span className="muted small"> · {analysis.description}</span>}
      </summary>
      {analysis.error ? (
        <p className="error-text small">{analysis.error}</p>
      ) : (
        <>
          <AnalysisView result={analysis} compact />
          {onOpen ? (
            <button className="button small-button" onClick={() => onOpen(analysis.spec)}>
              Open in Analyse
            </button>
          ) : null}
        </>
      )}
    </details>
  );
}

function QueryDetails({ query, index }: { query: QueryResult; index: number }) {
  return (
    <details className="query">
      <summary>
        Query {index + 1}
        {query.error ? (
          <span className="pill danger small-pill">error</span>
        ) : (
          <span className="muted small">
            {" "}
            · {formatCount(query.row_count)} row{query.row_count === 1 ? "" : "s"}
          </span>
        )}
      </summary>
      <pre className="sql">{query.sql}</pre>
      {query.error ? <p className="error-text small">{query.error}</p> : <DataTable columns={query.columns} rows={(query.rows ?? []).slice(0, 50)} />}
    </details>
  );
}

export function FormulaDetails({ check }: { check: FormulaCheck }) {
  const all = check.matches !== undefined && check.matches === check.rows_checked;
  return (
    <details className="query">
      <summary>
        Formula check: {check.target} = {check.expression}
        {check.error ? (
          <span className="pill danger small-pill">error</span>
        ) : (
          <span className={`pill ${all ? "success" : "warning"} small-pill`}>
            {formatCount(check.matches ?? 0)}/{formatCount(check.rows_checked ?? 0)} rows
          </span>
        )}
      </summary>
      {check.error ? (
        <p className="error-text small">{check.error}</p>
      ) : (
        <>
          <p className="muted small">
            Tolerance {check.tolerance}; largest difference {check.max_difference ?? "—"}
            {check.rows_blank ? `; ${check.rows_blank} rows had no value to check` : ""}.
          </p>
          {check.examples && check.examples.length > 0 ? (
            <DataTable columns={["Entry", "Actual", "Formula gives", "Difference"]} rows={check.examples.map((e) => [e.row, e.actual, e.expected, e.difference])} />
          ) : null}
        </>
      )}
    </details>
  );
}

/** Seconds since mount. */
function Elapsed() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return <>{seconds}s</>;
}

function Work({ result, onOpenAnalysis }: { result: ChatResult; onOpenAnalysis?: (spec: AnalysisSpec) => void }) {
  return (
    <div className="queries">
      {(result.analyses ?? []).map((analysis, index) => (
        <AnalysisDetails key={`a${index}`} analysis={analysis} onOpen={onOpenAnalysis} />
      ))}
      {result.queries.map((query, index) => (
        <QueryDetails key={`q${index}`} query={query} index={index} />
      ))}
      {(result.formula_checks ?? []).map((check, index) => (
        <FormulaDetails key={`f${index}`} check={check} />
      ))}
      {result.calculations?.length ? (
        <details className="query">
          <summary>
            Calculations <span className="muted small"> · {result.calculations.length}</span>
          </summary>
          <ul className="calc-list">
            {result.calculations.map((c, index) => (
              <li key={index}>
                <code>{c.expression}</code> = {c.error ? <span className="error-text">{c.error}</span> : <strong>{c.result}</strong>}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

/** Only file drags show the drop overlay; dragging selected text does not. */
function hasFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
}

function FileCard({ file, progress }: { file: SharedFile | File; progress?: string }) {
  const kinds = "kinds" in file ? file.kinds : undefined;
  return (
    <span className="file-card">
      <span className="file-icon">{Icon.file}</span>
      <span className="file-text">
        <span className="file-name" title={file.name}>
          {file.name}
        </span>
        <span className="file-meta">{progress ?? (kinds?.length ? kinds.join(" · ") : formatBytes(file.size))}</span>
      </span>
    </span>
  );
}

/** Markdown is parsed again only when the text changes. */
const Answer = memo(function Answer({ text, streaming = false }: { text: string; streaming?: boolean }) {
  return (
    <div className={`answer${streaming ? " streaming" : ""}`}>
      <Markdown remarkPlugins={REMARK_PLUGINS}>{text}</Markdown>
    </div>
  );
});

type TurnProps = {
  turn: Turn;
  last: boolean;
  canRegenerate: boolean;
  copied: boolean;
  workOpen: boolean;
  /** Upload progress by file name (only for the turn being sent). */
  progress?: Record<string, string>;
  showCompare: boolean;
  comparing: boolean;
  compareError: string | null;
  onCopy: (turnId: number, text: string) => void;
  onRegenerate: () => void;
  onToggleWork: (turnId: number) => void;
  onCompare: () => void;
  onOpenAnalysis?: (spec: AnalysisSpec) => void;
};

/** One question and its answer. Memoised: while an answer streams, earlier turns do not re-render. */
const TurnView = memo(function TurnView({
  turn,
  last,
  canRegenerate,
  copied,
  workOpen,
  progress,
  showCompare,
  comparing,
  compareError,
  onCopy,
  onRegenerate,
  onToggleWork,
  onCompare,
  onOpenAnalysis,
}: TurnProps) {
  const result = turn.result;
  return (
    <div className="turn">
      <div className="msg-user">
        {turn.files?.length ? (
          <div className="msg-files">
            {turn.files.map((f, i) => (
              <FileCard key={i} file={f} progress={progress?.[f.name]} />
            ))}
          </div>
        ) : null}
        {turn.question ? <div className="msg-user-bubble">{turn.question}</div> : null}
      </div>
      <div className="msg-ai">
        {result ? (
          <>
            <Answer text={result.answer} />
            <div className="ai-actions">
              <button className="ai-action" onClick={() => onCopy(turn.id, result.answer)} aria-label="Copy" title={copied ? "Copied" : "Copy"}>
                {copied ? Icon.check : Icon.copy}
              </button>
              {canRegenerate ? (
                <button className="ai-action" onClick={onRegenerate} aria-label="Regenerate" title="Regenerate">
                  {Icon.again}
                </button>
              ) : null}
              {result.verification.status === "verified" ? (
                <span
                  className="ai-check ok"
                  title={`All ${result.verification.figures} figures match your data${result.verification.corrected ? " (after one automatic correction)" : ""}`}
                >
                  ✓ {result.verification.figures} figure{result.verification.figures === 1 ? "" : "s"} checked
                </span>
              ) : result.verification.status === "unverified" ? (
                <span className="ai-check warn">! Check {result.verification.unverified.join(", ")}</span>
              ) : null}
              {(result.analyses?.length ?? 0) + result.queries.length + (result.calculations?.length ?? 0) + (result.formula_checks?.length ?? 0) > 0 ? (
                <button className="ai-action text" onClick={() => onToggleWork(turn.id)} aria-expanded={workOpen}>
                  {workOpen ? "Hide work" : "Show work"}
                </button>
              ) : null}
            </div>
            {workOpen ? <Work result={result} onOpenAnalysis={onOpenAnalysis} /> : null}
            {showCompare ? (
              <>
                <button className="compare-button" onClick={onCompare} disabled={comparing} aria-busy={comparing}>
                  {comparing ? "Opening the report…" : "Open the full report: GST, gross profit, party ledgers →"}
                </button>
                {compareError ? (
                  <p className="error-text small compare-error" role="alert">
                    {compareError}
                  </p>
                ) : null}
              </>
            ) : null}
          </>
        ) : turn.stopped ? (
          <>
            {turn.partial ? <Answer text={turn.partial} /> : null}
            <p className="muted small">Stopped. Figures in a stopped answer are not checked.</p>
          </>
        ) : turn.error ? (
          <div className="ai-error" role="alert">
            {turn.error}
            {last ? (
              <button className="link-button" onClick={onRegenerate}>
                Try again
              </button>
            ) : null}
          </div>
        ) : (
          <>
            {turn.live?.note ? <p className="muted small">{turn.live.note}</p> : null}
            {turn.live?.text ? null : (
              <p className="ai-step" role="status">
                <span className="thinking-dot" aria-hidden="true" />
                <span className="shimmer">{turn.live?.steps.at(-1) ?? "Thinking"}</span>
                {/* Hidden from screen readers: inside the status line it would be read out again every second. */}
                <span className="ai-elapsed" aria-hidden="true">
                  <Elapsed />
                </span>
              </p>
            )}
            {turn.live?.analysis && !turn.live.text ? <AnalysisView result={turn.live.analysis} compact /> : null}
            {turn.live?.text ? <Answer text={turn.live.text} streaming /> : null}
          </>
        )}
      </div>
    </div>
  );
});

// --- the chat --------------------------------------------------------------------------------------

type SendOptions = {
  fresh?: boolean;
  files?: File[];
  /** Read the conversation's documents again (a retry after the upload or the documents step failed). */
  refresh?: boolean;
  before?: Turn[];
  /** What the turn displays when it is a regenerated one (the original question and file cards). */
  shown?: Pick<Turn, "question" | "files">;
};

/** Delta text not yet shown: flushed to state at most once per animation frame. */
type StreamBuffer = { turnId: number; text: string; frame: number };

/** A ChatGPT-style conversation about the data: streamed answers, every figure checked, files can be attached. */
export default function ChatPanel({ scope, subject, suggestionList, health, stream, tables = [], defaultTable = "", runSql: executeSql, onOpenAnalysis, page = false, onLibrary, attachments }: Props) {
  const providers = health?.providers ?? [];
  // No model picker: the backend's default model (GPT-6 Luna) answers, or whichever model has a key.
  const selected = providers.find((p) => p.id === health?.default_provider && p.configured) ?? providers.find((p) => p.configured) ?? providers[0];

  const [chats, setChats] = useState<Conversation[]>(() => loadChats(scope));
  const [activeId, setActiveId] = useState<string | null>(null);
  const [mode, setMode] = useState<"chat" | "sql">("chat");
  const [sidebarClosed, setSidebarClosed] = useState(() => {
    try {
      return page && localStorage.getItem(SIDEBAR_KEY) === "closed";
    } catch {
      return false;
    }
  });
  const [narrow, setNarrow] = useState(() => window.matchMedia(NARROW).matches);
  const [search, setSearch] = useState<string | null>(null);
  const [attachMenu, setAttachMenu] = useState(false);
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  // Drag events fire on every child the pointer crosses, so count enters and leaves instead of trusting one leave.
  const dragDepth = useRef(0);
  const [openWork, setOpenWork] = useState<number | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [stuck, setStuck] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState<{ chatId: string; message: string } | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sendRef = useRef<HTMLButtonElement>(null);
  /** Where focus goes back to after the first question swaps the welcome layout for the conversation (new DOM nodes). */
  const refocus = useRef<"input" | "send" | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const asideRef = useRef<HTMLElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bufferRef = useRef<StreamBuffer | null>(null);
  /** Files that failed to upload, by turn id, so "Try again" uploads them again. */
  const retryFiles = useRef(new Map<number, File[]>());
  const drawerWasOpen = useRef(false);

  const [sql, setSql] = useState(() => defaultSql(defaultTable));
  const [sqlResult, setSqlResult] = useState<QueryResult | null>(null);
  const [sqlError, setSqlError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const ready = selected?.configured ?? false;
  const active = chats.find((c) => c.id === activeId) ?? null;
  const turns = active?.turns ?? [];
  const streaming = chats.some((c) => c.turns.some((t) => t.live));

  // The latest render's values, for the stable callbacks handed to the memoised turns and for the unmount cleanup.
  const latest = useRef({ scope, chats, send, regenerate, compare, onOpenAnalysis });
  useLayoutEffect(() => {
    latest.current = { scope, chats, send, regenerate, compare, onOpenAnalysis };
  });

  // Saved when nothing is streaming (a turn settled, or a chat was created, renamed or deleted), not on every token.
  useEffect(() => {
    if (streaming) return;
    if (!saveChats(scope, chats)) setNotice(NOT_SAVED);
  }, [scope, chats, streaming]);

  // Leaving mid-answer (e.g. "← Chat" from a file's chat): stop the request and keep what was written as a stopped turn.
  useEffect(
    () => () => {
      const { scope: lastScope, chats: lastChats } = latest.current;
      const buffer = bufferRef.current;
      abortRef.current?.abort();
      if (!lastChats.some((c) => c.turns.some((t) => t.live))) return;
      saveChats(
        lastScope,
        lastChats.map((c) => ({
          ...c,
          turns: c.turns.map((t) =>
            t.live ? { ...t, stopped: true, partial: t.live.text + (buffer?.turnId === t.id ? buffer.text : ""), live: undefined } : t,
          ),
        })),
      );
    },
    [],
  );

  // The first question remounts the composer (welcome layout -> conversation layout): put focus back where it was.
  useLayoutEffect(() => {
    const target = refocus.current;
    if (!target || !turns.length) return;
    refocus.current = null;
    const focused = document.activeElement;
    if (focused && focused !== document.body) return;
    (target === "input" ? inputRef : sendRef).current?.focus({ preventScroll: true });
  }, [turns.length]);

  useEffect(() => {
    if (health) setNotice((current) => (current === CONNECTING ? null : current));
  }, [health]);

  useEffect(() => {
    if (!page) return;
    try {
      localStorage.setItem(SIDEBAR_KEY, sidebarClosed ? "closed" : "open");
    } catch {
      // Not kept; the sidebar simply opens again next time.
    }
  }, [page, sidebarClosed]);

  useEffect(() => {
    const query = window.matchMedia(NARROW);
    const onChange = () => setNarrow(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  // Phones: focus moves into the drawer when it opens and back to "Open sidebar" when it closes.
  useEffect(() => {
    if (!narrow) {
      drawerWasOpen.current = false;
      return;
    }
    if (historyOpen) {
      asideRef.current?.querySelector<HTMLElement>("button, input")?.focus();
    } else if (drawerWasOpen.current) {
      const focused = document.activeElement;
      if (!focused || focused === document.body || asideRef.current?.contains(focused)) menuRef.current?.focus();
    }
    drawerWasOpen.current = historyOpen;
  }, [historyOpen, narrow]);

  // Escape closes the + menu and the phone sidebar, as in ChatGPT.
  useEffect(() => {
    if (!attachMenu && !historyOpen) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        setAttachMenu(false);
        setHistoryOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [attachMenu, historyOpen]);

  /** Phones: the sidebar slides in over the chat. Wider screens: it is shown or hidden beside it. */
  function toggleSidebar(open: boolean) {
    if (window.matchMedia(NARROW).matches) setHistoryOpen(open);
    else setSidebarClosed(!open);
  }

  // Follow the answer as it grows, unless the person scrolled up to read.
  useEffect(() => {
    const box = scrollRef.current;
    if (box && stuck) box.scrollTop = box.scrollHeight;
  }, [turns, stuck]);

  function onScroll() {
    const box = scrollRef.current;
    if (box) setStuck(box.scrollHeight - box.scrollTop - box.clientHeight < 80);
  }

  function grow() {
    const box = inputRef.current;
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, 200)}px`;
  }

  function updateChat(id: string, change: (c: Conversation) => Conversation) {
    setChats((list) => list.map((c) => (c.id === id ? change(c) : c)));
  }

  function updateTurn(chatId: string, turnId: number, change: (t: Turn) => Turn) {
    updateChat(chatId, (c) => ({ ...c, updated: Date.now(), turns: c.turns.map((t) => (t.id === turnId ? change(t) : t)) }));
  }

  /** Repeated text is still read out: alternate a trailing no-break space. */
  function announce(text: string) {
    setAnnouncement((current) => (current === text ? `${text} ` : text));
  }

  function newChat() {
    if (sending) return;
    setActiveId(null);
    setFiles([]);
    setDraft("");
    setHistoryOpen(false);
    setMode("chat");
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

  function addFiles(list: FileList | File[]) {
    const accepted = [...list].filter((f) => ACCEPTED.some((ext) => f.name.toLowerCase().endsWith(ext)));
    if (accepted.length < [...list].length) setNotice(`Only Excel and CSV files can be shared (${ACCEPTED.join(", ")}).`);
    setFiles((current) => [...current, ...accepted].slice(0, 6));
    if (accepted.length) void api.warmAi(); // a question about them is coming: open the connection now
  }

  /** Why a question cannot be sent yet, or null. */
  function blocked(): string | null {
    if (!health) return CONNECTING;
    if (!selected) return "The server has no AI model set up.";
    if (!ready) return `${selected.label} needs an API key in backend/.env.`;
    return null;
  }

  /** Upload ids in ``ids`` that the backend no longer has (deleted from the library). */
  async function missingUploads(ids: number[]): Promise<number[]> {
    try {
      const existing = new Set((await api.datasets()).map((d) => d.id));
      return ids.filter((id) => !existing.has(id));
    } catch {
      return [];
    }
  }

  async function send(text: string, options: SendOptions = {}) {
    const typed = text.trim();
    const toUpload = options.files ?? files;
    if ((!typed && !toUpload.length) || sending) return;
    const problem = blocked();
    if (problem || !selected) return setNotice(problem);
    setNotice(null);
    if (!turns.length) {
      const focused = document.activeElement;
      refocus.current = focused === inputRef.current ? "input" : focused instanceof HTMLElement && focused.closest(".chat-empty") ? "send" : null;
    }
    setSending(true);
    if (!options.shown) {
      setDraft("");
      setFiles([]);
      window.setTimeout(grow, 0);
    }

    // A new conversation starts with the first question (or the first file).
    let chatId = activeId;
    if (!chatId) {
      chatId = `c${Date.now()}`;
      const title = (typed || toUpload.map((f) => f.name).join(", ")).slice(0, 60);
      const created: Conversation = { id: chatId, title, updated: Date.now(), datasetIds: [], documents: [], turns: [] };
      setChats((list) => [created, ...list]);
      setActiveId(chatId);
    }
    const id = Date.now();
    const shared: SharedFile[] = toUpload.map((f) => ({ name: f.name, size: f.size }));
    let prompt = typed || (toUpload.length > 1 ? "Explain the files I just shared: which is which, and what each contains." : "Explain the file I just shared.");
    const before = options.before ?? chats.find((c) => c.id === chatId)?.turns ?? [];
    const question = options.shown?.question ?? typed;
    const cards = options.shown?.files ?? shared;
    updateChat(chatId, (c) => ({ ...c, updated: Date.now(), turns: [...c.turns, { id, question, prompt, files: cards, live: { steps: [], text: "" } }] }));
    setStuck(true);

    // Stop works from the start: it cancels uploads still in progress as well as the answer.
    const controller = new AbortController();
    abortRef.current = controller;
    const buffer: StreamBuffer = { turnId: id, text: "", frame: 0 };
    bufferRef.current = buffer;
    const takeBuffer = () => {
      if (buffer.frame) cancelAnimationFrame(buffer.frame);
      buffer.frame = 0;
      const text = buffer.text;
      buffer.text = "";
      return text;
    };
    let finished = false;
    let datasetIds = chats.find((c) => c.id === chatId)?.datasetIds ?? [];
    try {
      // Upload the attached files first (all at once, each with its progress), then ask about all of the conversation's files.
      if (attachments && (toUpload.length || options.refresh)) {
        if (toUpload.length) {
          updateTurn(chatId, id, (t) => ({ ...t, live: { steps: [toUpload.length > 1 ? `Uploading ${toUpload.length} files…` : `Uploading ${toUpload[0].name}…`], text: "" } }));
          const settled = await Promise.allSettled(
            toUpload.map((file) =>
              uploadFile(file, (p) => !finished && setUploading((u) => ({ ...u, [file.name]: `${Math.round(p * 100)}%` })), controller.signal),
            ),
          );
          const done: { file: File; detail: DatasetDetail }[] = [];
          const failed: File[] = [];
          let failure: Error | null = null;
          settled.forEach((outcome, i) => {
            if (outcome.status === "fulfilled") {
              done.push({ file: toUpload[i], detail: outcome.value });
              attachments.onUploaded(outcome.value);
            } else {
              failed.push(toUpload[i]);
              failure ??= outcome.reason as Error;
            }
          });
          setUploading({});
          // Files that did upload belong to the conversation even when a sibling failed.
          if (done.length) {
            const added = done.map((d) => d.detail.id);
            datasetIds = [...new Set([...datasetIds, ...added])];
            updateChat(chatId, (c) => ({
              ...c,
              datasetIds: [...new Set([...c.datasetIds, ...added])],
              turns: c.turns.map((t) => (t.id === id ? { ...t, files: linkCards(t.files, done) } : t)),
            }));
          }
          if (failed.length) {
            retryFiles.current.set(id, failed);
            if (controller.signal.aborted) throw new DOMException("Upload stopped", "AbortError");
            throw new Error(`${failed.map((f) => f.name).join(", ")} could not be uploaded. ${(failure as Error | null)?.message ?? ""}`.trim());
          }
        }
        updateTurn(chatId, id, (t) => ({ ...t, live: { steps: ["Reading the files…"], text: "" } }));
        const documents = datasetIds.length ? await api.documents(datasetIds) : [];
        // A sales register and a purchase register (now or with files shared earlier): analyse them together.
        const asked = options.shown ? options.shown.question.trim() : typed;
        if (!asked && documents.some((d) => d.kind === "sales") && documents.some((d) => d.kind === "purchases")) {
          prompt =
            "Explain the files I just shared (which is the sales register and which is the purchase register), then analyse " +
            "the two together: sales vs purchases, margin, GST payable after input tax credit, month by month, items, and anything I should check.";
        }
        const ids = datasetIds;
        updateChat(chatId, (c) => ({
          ...c,
          datasetIds: ids,
          documents,
          turns: c.turns.map((t) =>
            t.id === id
              ? {
                  ...t,
                  prompt,
                  files: (t.files ?? []).map((f) =>
                    f.datasetId === undefined ? f : { ...f, kinds: documents.filter((d) => d.dataset_id === f.datasetId).map((d) => d.label) },
                  ),
                }
              : t,
          ),
        }));
      }

      const flush = () => {
        const text = takeBuffer();
        if (text) updateTurn(chatId!, id, (t) => ({ ...t, live: { ...(t.live ?? { steps: [], text: "" }), text: (t.live?.text ?? "") + text } }));
      };
      const onEvent = (event: ChatEvent) => {
        if (event.type === "delta") {
          buffer.text += event.text;
          if (!buffer.frame) buffer.frame = requestAnimationFrame(flush);
          return;
        }
        if (event.type === "reset") takeBuffer();
        else flush();
        updateTurn(chatId!, id, (t) => {
          const live = t.live ?? { steps: [], text: "" };
          if (event.type === "step") return { ...t, live: { ...live, steps: [...live.steps, event.text].slice(-3) } };
          if (event.type === "reset") return { ...t, live: { ...live, text: "", note: event.text } };
          if (event.type === "analysis") return { ...t, live: { ...live, analysis: event.result } };
          return t;
        });
      };
      const result = await stream([...history(before), { role: "user", content: prompt }], selected.id, onEvent, {
        fresh: options.fresh,
        signal: controller.signal,
        datasetIds,
      });
      takeBuffer();
      updateTurn(chatId, id, (t) => ({ ...t, result, live: undefined }));
      announce(readyText(result));
    } catch (error) {
      const rest = takeBuffer();
      if ((error as Error).name === "AbortError") {
        updateTurn(chatId, id, (t) => ({ ...t, stopped: true, partial: (t.live?.text ?? "") + rest, live: undefined }));
        announce("Stopped.");
      } else {
        let message = (error as Error).message;
        // A shared file was deleted from the library: drop it from the conversation instead of failing on every question.
        if (attachments && error instanceof ApiError && error.status === 404 && datasetIds.length) {
          const gone = await missingUploads(datasetIds);
          if (gone.length) {
            const chat = latest.current.chats.find((c) => c.id === chatId);
            const names = [
              ...new Set(
                gone.map(
                  (g) =>
                    chat?.documents.find((d) => d.dataset_id === g)?.filename ??
                    chat?.turns.flatMap((t) => t.files ?? []).find((f) => f.datasetId === g)?.name ??
                    `Upload ${g}`,
                ),
              ),
            ];
            updateChat(chatId, (c) => ({
              ...c,
              datasetIds: c.datasetIds.filter((x) => !gone.includes(x)),
              documents: c.documents.filter((d) => !gone.includes(d.dataset_id)),
            }));
            const one = names.length === 1;
            message = `${names.join(", ")} ${one ? "was" : "were"} deleted from your files, so ${one ? "it was" : "they were"} removed from this chat. Try again to ask without ${one ? "it" : "them"}.`;
          }
        }
        updateTurn(chatId, id, (t) => ({ ...t, error: message, live: undefined }));
      }
    } finally {
      finished = true;
      if (abortRef.current === controller) abortRef.current = null;
      if (bufferRef.current === buffer) bufferRef.current = null;
      setUploading({});
      setSending(false);
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  function regenerate() {
    const last = turns.at(-1);
    if (!last || !active || sending) return;
    const problem = blocked();
    if (problem) return setNotice(problem);
    const retry = retryFiles.current.get(last.id) ?? [];
    retryFiles.current.delete(last.id);
    updateChat(active.id, (c) => ({ ...c, turns: c.turns.slice(0, -1) }));
    void send(last.prompt ?? last.question, {
      fresh: true,
      files: retry,
      refresh: Boolean(last.error && last.files?.length),
      before: turns.slice(0, -1),
      shown: { question: last.question, files: last.files },
    });
  }

  async function compare() {
    if (!attachments || !active || comparing) return;
    const chatId = active.id;
    setComparing(true);
    setCompareError(null);
    try {
      await attachments.onCompare(active.documents, active.title || "Sales vs purchases");
    } catch (error) {
      setCompareError({ chatId, message: (error as Error).message });
    } finally {
      setComparing(false);
    }
  }

  // Stable callbacks, so the memoised turns do not re-render on every streamed token.
  const onCopy = useCallback((turnId: number, text: string) => {
    void copyText(text);
    setCopied(turnId);
    window.setTimeout(() => setCopied(null), 1500);
  }, []);
  const onToggleWork = useCallback((turnId: number) => setOpenWork((open) => (open === turnId ? null : turnId)), []);
  const onRegenerate = useCallback(() => latest.current.regenerate(), []);
  const onCompare = useCallback(() => void latest.current.compare(), []);
  const openAnalysis = useCallback((spec: AnalysisSpec) => latest.current.onOpenAnalysis?.(spec), []);

  async function runSql() {
    if (!executeSql || !sql.trim() || running) return;
    setRunning(true);
    setSqlError(null);
    try {
      setSqlResult(await executeSql(sql));
    } catch (error) {
      setSqlResult(null);
      setSqlError((error as Error).message);
    } finally {
      setRunning(false);
    }
  }

  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(draft);
    }
  }

  // A drag that is cancelled, dropped elsewhere or leaves the window must not leave the overlay showing.
  useEffect(() => {
    if (!dragging) return;
    const reset = () => {
      dragDepth.current = 0;
      setDragging(false);
    };
    const onLeave = (event: globalThis.DragEvent) => {
      if (!event.relatedTarget) reset();
    };
    window.addEventListener("dragend", reset);
    window.addEventListener("drop", reset);
    window.addEventListener("dragleave", onLeave);
    return () => {
      window.removeEventListener("dragend", reset);
      window.removeEventListener("drop", reset);
      window.removeEventListener("dragleave", onLeave);
    };
  }, [dragging]);

  function onDrop(event: DragEvent) {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (attachments && event.dataTransfer.files.length) addFiles(event.dataTransfer.files);
  }

  const kinds = new Set((active?.documents ?? []).map((d) => d.kind));
  const canCompare = Boolean(attachments && kinds.has("sales") && kinds.has("purchases"));
  const query = search?.trim().toLowerCase() ?? "";
  const listed = query ? chats.filter((c) => c.title.toLowerCase().includes(query)) : chats;
  const empty = !draft.trim() && !files.length;

  const composer = (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        void send(draft);
      }}
    >
      {notice ? <p className="composer-notice">{notice}</p> : null}
      <div className="composer-box">
        {files.length ? (
          <div className="composer-files">
            {files.map((f, i) => (
              <span className="composer-file" key={`${f.name}${i}`}>
                <FileCard file={f} />
                <button type="button" className="file-remove" aria-label={`Remove ${f.name}`} onClick={() => setFiles((list) => list.filter((_, j) => j !== i))}>
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <div className="composer-row">
          {attachments ? (
            <span className="attach-wrap">
              <button
                type="button"
                className="composer-attach"
                onClick={() => (onLibrary ? setAttachMenu((open) => !open) : fileRef.current?.click())}
                aria-label="Add files"
                aria-haspopup={onLibrary ? "menu" : undefined}
                aria-expanded={onLibrary ? attachMenu : undefined}
                title="Add files"
                disabled={sending}
              >
                {Icon.plus}
              </button>
              {attachMenu && onLibrary ? (
                <span className="popover attach-menu" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    className="menu-item"
                    onClick={() => {
                      setAttachMenu(false);
                      fileRef.current?.click();
                    }}
                  >
                    {Icon.clip}
                    <span className="menu-text">
                      Add Excel or CSV files
                      <span className="menu-sub">Sales, purchases, bank statement, ledger</span>
                    </span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className="menu-item"
                    onClick={() => {
                      setAttachMenu(false);
                      onLibrary();
                    }}
                  >
                    {Icon.folder}
                    <span className="menu-text">
                      Your files and company books
                      <span className="menu-sub">Earlier uploads, vouchers, gold ledger</span>
                    </span>
                  </button>
                </span>
              ) : null}
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPTED.join(",")}
                multiple
                hidden
                onChange={(e) => {
                  if (e.target.files) addFiles(e.target.files);
                  e.target.value = "";
                }}
              />
            </span>
          ) : null}
          <textarea
            ref={inputRef}
            value={draft}
            rows={1}
            onChange={(e) => {
              setDraft(e.target.value);
              grow();
            }}
            onKeyDown={onKey}
            onFocus={() => void api.warmAi()}
            placeholder={attachments ? "Ask anything" : `Ask anything about ${subject}`}
            maxLength={2000}
            aria-label="Message"
          />
          {/* One button for Send and Stop, so focus stays on it when it switches; aria-disabled keeps it focusable.
              Always type="button": a type that turns to "submit" during the Stop click would submit the form (and send the draft). */}
          <button
            ref={sendRef}
            type="button"
            className={`send-button${sending ? " stop" : ""}`}
            onClick={sending ? stop : () => void send(draft)}
            aria-disabled={!sending && empty ? true : undefined}
            aria-label={sending ? "Stop answering" : "Send"}
            title={sending ? "Stop" : "Send"}
          >
            {sending ? Icon.stop : Icon.send}
          </button>
        </div>
      </div>
      <p className="composer-note">Accounts.ai checks every figure against your data, but can still make mistakes.</p>
    </form>
  );

  return (
    <section className={`chatgpt${page ? " page" : ""}${historyOpen ? " history-open" : ""}${sidebarClosed ? " sidebar-closed" : ""}`}>
      <aside className="chat-history" aria-label="Chats" ref={asideRef} inert={narrow && !historyOpen}>
        <div className="history-top">
          {page ? (
            <button className="history-logo" onClick={newChat} aria-label="New chat" title="New chat">
              A
            </button>
          ) : (
            <span />
          )}
          <button className="icon-button history-toggle" onClick={() => toggleSidebar(false)} aria-label="Close sidebar" title="Close sidebar">
            {Icon.sidebar}
          </button>
        </div>
        <button className="history-row" onClick={newChat}>
          {Icon.edit} New chat
        </button>
        <button className={`history-row${search !== null ? " active" : ""}`} onClick={() => setSearch(search === null ? "" : null)}>
          {Icon.search} Search chats
        </button>
        {search !== null ? (
          <input
            className="history-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setSearch(null);
            }}
            placeholder="Search chats"
            aria-label="Search chats"
            autoFocus
          />
        ) : null}
        <p className="history-label">{chats.length ? (query ? `${listed.length} found` : "Chats") : "No chats yet"}</p>
        <ul>
          {listed.map((c) => (
            <li key={c.id} className={c.id === activeId ? "active" : undefined}>
              <button
                className="history-item"
                onClick={() => {
                  if (sending) return;
                  setActiveId(c.id);
                  setHistoryOpen(false);
                  setMode("chat");
                }}
                title={c.title}
              >
                {c.title || "Conversation"}
              </button>
              <button
                className="history-delete"
                aria-label={`Delete ${c.title}`}
                title="Delete chat"
                onClick={() => {
                  if (sending && c.id === activeId) return;
                  if (!window.confirm(`Delete the chat "${c.title || "Conversation"}"? This cannot be undone.`)) return;
                  c.turns.forEach((t) => retryFiles.current.delete(t.id));
                  setChats((list) => list.filter((x) => x.id !== c.id));
                  if (c.id === activeId) setActiveId(null);
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        {executeSql ? (
          <button
            className="link-button history-sql"
            onClick={() => {
              setMode("sql");
              setHistoryOpen(false);
            }}
          >
            Advanced: SQL
          </button>
        ) : null}
      </aside>
      {historyOpen ? <div className="history-backdrop" onClick={() => setHistoryOpen(false)} /> : null}
      {attachMenu ? <div className="popover-backdrop" onClick={() => setAttachMenu(false)} /> : null}
      <p className="chat-sr-only" aria-live="polite">
        {announcement}
      </p>

      <div
        className={`chat-main${dragging ? " dragging" : ""}`}
        onDragEnter={(e) => {
          if (!attachments || !hasFiles(e)) return;
          e.preventDefault();
          dragDepth.current += 1;
          setDragging(true);
        }}
        onDragOver={(e) => {
          if (attachments && hasFiles(e)) e.preventDefault();
        }}
        onDragLeave={() => {
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (dragDepth.current === 0) setDragging(false);
        }}
        onDrop={onDrop}
      >
        <header className="chat-top">
          <button ref={menuRef} className="icon-button chat-menu" onClick={() => toggleSidebar(true)} aria-label="Open sidebar" title="Open sidebar" aria-expanded={narrow ? historyOpen : undefined}>
            {Icon.sidebar}
          </button>
          <span className="chat-subject" title={page ? undefined : subject}>
            {mode === "sql" ? "SQL (advanced)" : page ? "" : active?.title ?? subject}
          </span>
          <button className="icon-button chat-new" onClick={newChat} aria-label="New chat" title="New chat">
            {Icon.edit}
          </button>
        </header>

        {mode === "sql" ? (
          <div className="chat-sql">
            <button className="link-button" onClick={() => setMode("chat")}>
              ← Back to the chat
            </button>
            <div className="chips">
              {tables.map((sheet) => (
                <button key={sheet.table_name} className="chip mono" onClick={() => setSql(defaultSql(sheet.table_name))} title={`Sheet: ${sheet.sheet_name}`}>
                  {sheet.table_name}
                </button>
              ))}
            </div>
            <textarea
              className="sql-input"
              value={sql}
              onChange={(event) => setSql(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault();
                  void runSql();
                }
              }}
              rows={5}
              spellCheck={false}
              aria-label="SQL query"
            />
            <div className="sql-actions">
              <button className="button primary" onClick={() => void runSql()} disabled={running || !sql.trim()}>
                {running ? "Running…" : "Run query"}
              </button>
              <span className="muted small">Read-only DuckDB SELECT · Ctrl+Enter to run</span>
            </div>
            {sqlError ? <p className="error-text">{sqlError}</p> : null}
            {sqlResult ? (
              <>
                <p className="muted small">
                  {formatCount(sqlResult.row_count)} row{sqlResult.row_count === 1 ? "" : "s"}
                  {sqlResult.truncated ? " (limited)" : ""} · {sqlResult.elapsed_ms} ms
                </p>
                <DataTable columns={sqlResult.columns} rows={sqlResult.rows} />
              </>
            ) : null}
          </div>
        ) : turns.length === 0 ? (
          // A new chat: the question in the middle of the screen, the box right under it (phones: at the bottom).
          <div className="chat-empty">
            <div className="chat-welcome">
              <h1>{attachments ? "What can I help with?" : `Ask about ${subject}`}</h1>
              {attachments ? null : <p className="muted">Every figure in an answer is checked against your data.</p>}
            </div>
            {composer}
            <div className="welcome-pills">
              {suggestionList.map((s) => {
                const attach = Boolean(attachments) && s.startsWith("+");
                return (
                  <button key={s} className="welcome-pill" onClick={() => (attach ? fileRef.current?.click() : void send(s))} disabled={sending}>
                    {attach ? Icon.clip : null}
                    <span>{attach ? s.slice(1).trim() : s}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <>
            <div className="chat-scroll" ref={scrollRef} onScroll={onScroll}>
              <div className="chat-column">
                {turns.map((turn, index) => {
                  const last = index === turns.length - 1;
                  return (
                    <TurnView
                      key={turn.id}
                      turn={turn}
                      last={last}
                      canRegenerate={last && !sending}
                      copied={copied === turn.id}
                      workOpen={openWork === turn.id}
                      progress={turn.live ? uploading : undefined}
                      showCompare={last && canCompare}
                      comparing={last && comparing}
                      compareError={last && compareError && compareError.chatId === active?.id ? compareError.message : null}
                      onCopy={onCopy}
                      onRegenerate={onRegenerate}
                      onToggleWork={onToggleWork}
                      onCompare={onCompare}
                      onOpenAnalysis={onOpenAnalysis ? openAnalysis : undefined}
                    />
                  );
                })}
              </div>
            </div>

            {!stuck ? (
              <button className="jump-bottom" aria-label="Jump to the latest" onClick={() => setStuck(true)}>
                ↓
              </button>
            ) : null}

            {composer}
          </>
        )}
        {dragging ? <div className="drop-overlay">Drop Excel files to share them</div> : null}
      </div>
    </section>
  );
}
