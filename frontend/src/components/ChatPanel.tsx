import { useMemo, useRef, useState } from "react";
import { formatCount } from "../format";
import type { AnalysisSpec, Health, QueryResult, Sheet as DataSheet } from "../types";
import { Button, Chip, ChipGroup, Composer, Icon, Input, Notice, Sheet, TextArea } from "../ui";
import { deleteChat, type Conversation } from "../screens/home/chatStore";
import { ChatThread } from "../screens/home/ChatThread";
import { dayLabel } from "../screens/home/chatUtils";
import { useChatEngine, type ChatStream } from "../screens/home/useChatEngine";
import { useFollow } from "../screens/home/useFollow";
import { useSpeech } from "../screens/home/useSpeech";
import DataTable from "./DataTable";
import "../screens/home/ChatPanel.css";

// The conversation store and the work details live with Home's chat; these names are kept for older imports.
export { forgetChats, forgetDataset, serializeChats, sweepChats } from "../screens/home/chatStore";
export { FormulaDetails } from "../screens/home/Work";
export type { ChatStream } from "../screens/home/useChatEngine";

type TableRef = { table_name: string; sheet_name: string };

type Props = {
  /** Where this chat's conversations are kept on this device, e.g. "ds-2" or "book-1". */
  scope: string;
  /** What the chat is about: a file name or a sales + purchases set. */
  subject: string;
  suggestionList: string[];
  health: Health | null;
  stream: ChatStream;
  /** Advanced SQL over the same tables (behind a button). */
  tables?: TableRef[];
  defaultTable?: string;
  runSql?: (sql: string) => Promise<QueryResult>;
  /** Open one of the AI's analyses in the Analyse screen. */
  onOpenAnalysis?: (spec: AnalysisSpec) => void;
};

/** Starter questions based on the columns the backend recognised in the sheet. */
export function suggestions(sheet: DataSheet): string[] {
  const { detected } = sheet.profile.summary;
  const label = (name: string | null) => sheet.profile.columns.find((c) => c.name === name)?.label.toLowerCase() ?? name ?? "";
  const measure = detected.amount ?? detected.credit;
  const out: string[] = [];
  if (detected.debit && detected.credit && detected.date) {
    out.push(`What are total ${label(detected.debit)} and ${label(detected.credit)} for each month?`);
  }
  if (detected.category && measure) out.push(`Which ${label(detected.category)} has the highest ${label(measure)}?`);
  if (detected.amount) out.push(`Show the 5 largest entries by ${label(detected.amount)}.`);
  if (detected.tax.length && detected.date) out.push(`How much ${label(detected.tax[0])} is there each month?`);
  out.push("Summarise this data in a few bullet points.");
  out.push("Which formulas link the number columns? Check them on every row.");
  return out.slice(0, 4);
}

function defaultSql(table: string): string {
  return `SELECT *\nFROM "${table}"\nLIMIT 20`;
}

/**
 * The AI chat of one uploaded file or one sales + purchases set, in the design's bubbles: its own conversations
 * (a side list on wide windows, a sheet on phones), the streamed answers and an advanced SQL view.
 */
export default function ChatPanel({ scope, subject, suggestionList, health, stream, tables = [], defaultTable = "", runSql: executeSql, onOpenAnalysis }: Props) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"chat" | "sql">("chat");
  const [listOpen, setListOpen] = useState(false);
  const [doomed, setDoomed] = useState<Conversation | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);

  const engine = useChatEngine({ scope, health, stream, activeId, onStarted: setActiveId, inputRef });
  const { active, turns, notice, setNotice } = engine;
  const speech = useSpeech(setText, setNotice);
  const follow = useFollow(mode === "chat" && turns.length > 0, mainRef, turns, active?.id ?? null);

  function open(id: string | null) {
    setActiveId(id);
    setMode("chat");
    setListOpen(false);
    if (id === null) {
      setText("");
      window.setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 0);
    }
  }

  function submit() {
    if (speech.listening) speech.stop();
    if (engine.ask(text)) setText("");
  }

  function remove() {
    if (!doomed) return;
    engine.forgetRetries(doomed);
    if (!deleteChat(scope, doomed.id)) setNotice("The list could not be saved on this device (storage is full or blocked).");
    if (doomed.id === activeId) setActiveId(null);
    setDoomed(null);
  }

  const list = (
    <ChatList
      chats={engine.chats}
      activeId={activeId}
      busyId={engine.sendingId}
      onOpen={open}
      onDelete={setDoomed}
      onSql={
        executeSql
          ? () => {
              setMode("sql");
              setListOpen(false);
            }
          : undefined
      }
    />
  );

  return (
    <section className="chat-panel">
      <aside className="chat-panel__side" aria-label="Chats">
        {list}
      </aside>

      <div className="chat-panel__main" ref={mainRef}>
        <div className="chat-panel__bar">
          <button type="button" className="chat-panel__btn chat-panel__chats" onClick={() => setListOpen(true)} aria-label="Chats" title="Chats">
            <Icon name="sidebar" size={18} />
          </button>
          <h2 className="chat-panel__title" title={active?.title ?? subject}>
            {mode === "sql" ? "SQL (advanced)" : active?.title || `Ask about ${subject}`}
          </h2>
          <button type="button" className="chat-panel__btn is-new" onClick={() => open(null)} title="New chat">
            <Icon name="edit" size={16} />
            <span>New chat</span>
          </button>
        </div>

        {mode === "sql" && executeSql ? (
          <SqlView tables={tables} defaultTable={defaultTable} run={executeSql} onBack={() => setMode("chat")} />
        ) : (
          <>
            {turns.length ? (
              <ChatThread engine={engine} onOpenAnalysis={onOpenAnalysis} />
            ) : (
              <div className="chat-panel__welcome">
                <h3>Ask about {subject}</h3>
                <p>Every figure in an answer is checked against your data.</p>
                <div className="chat-panel__ideas">
                  {suggestionList.map((s) => (
                    <button key={s} type="button" className="chat-suggest" onClick={() => engine.ask(s)} disabled={engine.sending}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="chat-panel__composer">
              {turns.length && !follow.stuck ? (
                <button type="button" className="chat-panel__jump" onClick={follow.jump} aria-label="Jump to the latest">
                  <Icon name="down" size={18} />
                </button>
              ) : null}
              <Composer
                value={text}
                onChange={setText}
                onSubmit={submit}
                placeholder={speech.listening ? "Listening…" : `Ask about ${subject}`}
                busy={engine.sending}
                onStop={engine.stop}
                onMic={speech.supported ? () => speech.toggle(text) : undefined}
                listening={speech.listening}
                inputRef={inputRef}
                above={
                  notice ? (
                    <p className="chat-panel__notice" role="status">
                      <span>{notice}</span>
                      <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss">
                        <Icon name="close" size={14} />
                      </button>
                    </p>
                  ) : null
                }
              />
              <p className="chat-panel__note">Accounts.ai checks every figure against your data, but can still make mistakes.</p>
            </div>
          </>
        )}
        <p className="visually-hidden" aria-live="polite">
          {engine.announcement}
        </p>
      </div>

      <Sheet open={listOpen} onClose={() => setListOpen(false)} title="Chats">
        {list}
      </Sheet>
      <Sheet
        open={doomed !== null}
        onClose={() => setDoomed(null)}
        title="Delete this chat?"
        description={`“${doomed?.title || "Conversation"}” will be removed from this device. This cannot be undone.`}
        actions={
          <>
            <Button onClick={() => setDoomed(null)} data-autofocus>
              Cancel
            </Button>
            <Button variant="danger" icon="trash" onClick={remove}>
              Delete
            </Button>
          </>
        }
      />
    </section>
  );
}

type ListProps = {
  chats: Conversation[];
  activeId: string | null;
  busyId: string | null;
  onOpen: (id: string | null) => void;
  onDelete: (chat: Conversation) => void;
  onSql?: () => void;
};

function ChatList({ chats, activeId, busyId, onOpen, onDelete, onSql }: ListProps) {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return chats.filter((c) => c.turns.length && (!q || c.title.toLowerCase().includes(q))).sort((a, b) => b.updated - a.updated);
  }, [chats, query]);
  const total = chats.filter((c) => c.turns.length).length;
  return (
    <div className="chat-panel__list">
      <button type="button" className="chat-panel__row is-new" onClick={() => onOpen(null)}>
        <Icon name="edit" size={16} /> New chat
      </button>
      {total > 5 ? (
        <Input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search chats" aria-label="Search chats" />
      ) : null}
      <p className="chat-panel__label">{total ? (query.trim() ? `${shown.length} found` : "Chats") : "No chats yet"}</p>
      <ul>
        {shown.map((c) => (
          <li key={c.id} className={c.id === activeId ? "is-active" : undefined}>
            <button type="button" className="chat-panel__item" onClick={() => onOpen(c.id)} title={c.title} aria-current={c.id === activeId || undefined}>
              <span>{c.title || "Conversation"}</span>
              <small>{dayLabel(c.updated)}</small>
            </button>
            {c.id === busyId ? null : (
              <button type="button" className="chat-panel__delete" onClick={() => onDelete(c)} aria-label={`Delete “${c.title || "Conversation"}”`} title="Delete chat">
                <Icon name="trash" size={15} />
              </button>
            )}
          </li>
        ))}
      </ul>
      {onSql ? (
        <button type="button" className="chat-panel__row" onClick={onSql}>
          <Icon name="grid" size={16} /> Advanced: SQL
        </button>
      ) : null}
    </div>
  );
}

type SqlProps = { tables: TableRef[]; defaultTable: string; run: (sql: string) => Promise<QueryResult>; onBack: () => void };

/** Read-only SQL over the same tables, for people who know it. */
function SqlView({ tables, defaultTable, run, onBack }: SqlProps) {
  const [sql, setSql] = useState(() => defaultSql(defaultTable));
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function execute() {
    if (!sql.trim() || running) return;
    setRunning(true);
    setError(null);
    try {
      setResult(await run(sql));
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="chat-panel__sql">
      <Button variant="ghost" size="sm" icon="back" onClick={onBack}>
        Back to the chat
      </Button>
      {tables.length ? (
        <ChipGroup label="Tables">
          {tables.map((t) => (
            <Chip key={t.table_name} pressed={sql.includes(`"${t.table_name}"`)} onClick={() => setSql(defaultSql(t.table_name))} title={`Sheet: ${t.sheet_name}`}>
              {t.table_name}
            </Chip>
          ))}
        </ChipGroup>
      ) : null}
      <TextArea
        className="chat-panel__sql-input"
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            void execute();
          }
        }}
        rows={6}
        spellCheck={false}
        aria-label="SQL query"
      />
      <div className="chat-panel__sql-actions">
        <Button variant="brand" onClick={() => void execute()} busy={running} disabled={!sql.trim()}>
          {running ? "Running…" : "Run query"}
        </Button>
        <span>Read-only DuckDB SELECT · Ctrl+Enter to run</span>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {result ? (
        <>
          <p className="chat-panel__sql-meta">
            {formatCount(result.row_count)} row{result.row_count === 1 ? "" : "s"}
            {result.truncated ? " (limited)" : ""} · {result.elapsed_ms} ms
          </p>
          <DataTable columns={result.columns} rows={result.rows} />
        </>
      ) : null}
    </div>
  );
}
