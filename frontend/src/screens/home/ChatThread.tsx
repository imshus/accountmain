import { memo, useEffect, useState, type ComponentPropsWithoutRef } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnalysisView } from "../../components/AnalysePanel";
import { formatCount } from "../../format";
import { navigate } from "../../router";
import type { AnalysisSpec, ChatImport, ChatResult, DocumentInfo, PendingRegister } from "../../types";
import { Icon, Spinner } from "../../ui";
import { MAX_PENDING, type SharedFile, type Turn } from "./chatStore";
import { answerLanguage, EXPLAIN_MANY, EXPLAIN_ONE, hasHow, registerReply, type ReplyLanguage } from "./chatUtils";
import type { ChatEngine } from "./useChatEngine";
import { Work } from "./Work";
import "./ChatThread.css";

const REMARK_PLUGINS = [remarkGfm];
// Wide tables scroll sideways inside the answer card instead of stretching the page.
const MD_COMPONENTS: Components = {
  table: (props: ComponentPropsWithoutRef<"table">) => (
    <div className="chat-md__table">
      <table {...props} />
    </div>
  ),
};

/** Markdown is parsed again only when the text changes. */
const Answer = memo(function Answer({ text, streaming = false }: { text: string; streaming?: boolean }) {
  return (
    <div className={`chat-md${streaming ? " is-streaming" : ""}`}>
      <Markdown remarkPlugins={REMARK_PLUGINS} components={MD_COMPONENTS}>
        {text}
      </Markdown>
    </div>
  );
});

/** Seconds since mount. */
function Elapsed() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return <>{seconds}s</>;
}

/** The design's mint banner for a shared file: name · what it is — status. */
function FileBanner({ file, turn, progress }: { file: SharedFile; turn: Turn; progress?: string }) {
  const kinds = file.kinds?.filter(Boolean).join(", ");
  let status: string;
  let tone = "";
  if (file.datasetId === undefined) {
    if (turn.live) status = progress ? `uploading… ${progress}` : "uploading…";
    else {
      status = "could not be uploaded.";
      tone = " is-failed";
    }
  } else if (turn.live && !file.kinds) status = "uploaded, reading it…";
  else status = "upload ho gayi, ab iske baare mein sawaal poochho.";
  return (
    <p className={`chat-file${tone}`}>
      <Icon name="file" size={16} />
      <span>
        <b>{file.name}</b>
        {kinds ? ` · ${kinds}` : ""} — {status}
      </span>
    </p>
  );
}

function Verified({ result }: { result: ChatResult }) {
  const check = result.verification;
  if (check.status === "verified") {
    const title = `All ${check.figures} figure${check.figures === 1 ? "" : "s"} match your data${check.corrected ? " (after one automatic correction)" : ""}`;
    return (
      <span className="chat-check" title={title}>
        <Icon name="check" size={13} stroke={2.2} />
        Every figure checked
        <span className="visually-hidden">: {title}.</span>
      </span>
    );
  }
  if (check.status === "unverified") {
    return (
      <span className="chat-check is-warn">
        <Icon name="alert" size={13} stroke={2.2} />
        Check {check.unverified.join(", ")}
      </span>
    );
  }
  return null;
}

const REGISTER_LABEL: Record<ChatImport["register"], string> = { sales: "Sales", purchases: "Purchase" };
const inBooks = (i: ChatImport) => i.created > 0 || i.skipped > 0;

/**
 * Sheets the AI added to the books: how many bills went in (or were already there, when it was asked again), and a
 * chip to each register they are in.
 */
function Imported({ imports }: { imports: ChatImport[] }) {
  const registers = [...new Set(imports.filter(inBooks).map((i) => i.register))];
  const skipped = imports.reduce((n, i) => n + i.skipped, 0);
  const parts = registers.flatMap((register) => {
    const bills = imports.filter((i) => i.register === register).reduce((n, i) => n + i.created, 0);
    return bills ? [`${formatCount(bills)} ${bills === 1 ? "bill" : "bills"} added to ${REGISTER_LABEL[register]}`] : [];
  });
  if (skipped) parts.push(`${formatCount(skipped)} already in the books`);
  return (
    <div className="chat-imported">
      <p className="chat-imported__note">
        <Icon name="check" size={13} stroke={2.2} />
        {parts.join(" · ")}
      </p>
      <div className="chat-followups" role="group" aria-label="Added to the books">
        {registers.map((register) => (
          <button key={register} type="button" className="chat-followup" onClick={() => navigate({ name: "register", kind: register })}>
            Open {REGISTER_LABEL[register]}
          </button>
        ))}
      </div>
    </div>
  );
}

const REGISTERS = ["sales", "purchases"] as const;
const REGISTER_ICON = { sales: "trend", purchases: "cart" } as const;

type PendingProps = { pending: PendingRegister[]; documents: DocumentInfo[]; language: ReplyLanguage; onReply: (text: string) => void };

/**
 * The answer asked whether shared sheets are sales or purchase data: a "Sales" and a "Purchase" chip per sheet (the
 * register its data points to highlighted), each sending the reply as if it was typed. Sheets are named whenever the
 * conversation has more than one (so the AI knows which), with the sheet's name when its file has others, and its table
 * when another upload has the same file and sheet (the same Excel shared twice).
 */
function PendingRegisters({ pending, documents, language, onReply }: PendingProps) {
  const rows = pending.slice(0, MAX_PENDING);
  const sheets = new Map(documents.map((d) => [d.table_name, { filename: d.filename, sheet: d.sheet_name }]));
  rows.forEach((p) => sheets.set(p.table, { filename: p.filename, sheet: p.sheet }));
  const nameOf = (p: PendingRegister) => {
    const file = p.filename || p.sheet || p.table;
    const others = [...sheets].filter(([table, s]) => table !== p.table && s.filename === p.filename).map(([, s]) => s.sheet);
    if (others.includes(p.sheet)) return `${file} (${p.table})`;
    return p.sheet && others.length ? `${file} (${p.sheet})` : file;
  };
  return (
    <div className="chat-registers">
      {rows.map((p, i) => {
        const name = sheets.size > 1 ? nameOf(p) : null;
        return (
          <div
            key={`${p.dataset_id}:${p.table}:${i}`}
            className="chat-register"
            role="group"
            aria-label={name ? `Is ${name} sales or purchase data?` : "Is this sales or purchase data?"}
          >
            {name ? <span className="chat-register__name">{name}</span> : null}
            {REGISTERS.map((register) => (
              <button
                key={register}
                type="button"
                className={`chat-followup chat-register__chip${p.suggestion === register ? " is-suggested" : ""}`}
                onClick={() => onReply(registerReply(register, name, language))}
              >
                <Icon name={REGISTER_ICON[register]} size={15} />
                {REGISTER_LABEL[register]}
                {p.suggestion === register ? <span className="visually-hidden"> (suggested)</span> : null}
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}

/** "how this was calculated": closed at first; the work is only drawn while it is open. */
function How({ result, steps, onOpenAnalysis }: { result: ChatResult; steps?: string[]; onOpenAnalysis?: (spec: AnalysisSpec) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="chat-how" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>how this was calculated</summary>
      {open ? <Work result={result} steps={steps} onOpenAnalysis={onOpenAnalysis} /> : null}
    </details>
  );
}

type TurnProps = {
  turn: Turn;
  last: boolean;
  /** Regenerate / Try again are offered (the last turn, nothing being written). */
  canRetry: boolean;
  copied: boolean;
  /** Upload progress by file name (only for the turn being sent). */
  progress?: Record<string, string>;
  showCompare: boolean;
  comparing: boolean;
  compareError: string | null;
  /** Suggested next questions (the latest answer, nothing being written). */
  followups?: string[];
  /** Shared sheets the answer asks "sales or purchase?" about (the latest answer, nothing being written). */
  pending?: PendingRegister[];
  /** The conversation's shared sheets (with pending: a chip names its file when there are others). */
  documents?: DocumentInfo[];
  /** The language those chips reply in: the one the answer was asked in. */
  language: ReplyLanguage;
  onCopy: (turnId: number, text: string) => void;
  onRegenerate: () => void;
  onCompare: () => void;
  onAsk?: (question: string, prompt: string) => void;
  onFollowup: (question: string) => void;
  onOpenAnalysis?: (spec: AnalysisSpec) => void;
};

/** One exchange: shared files, the question and the answer. Memoised: while an answer streams, earlier turns do not re-render. */
const TurnView = memo(function TurnView({
  turn,
  last,
  canRetry,
  copied,
  progress,
  showCompare,
  comparing,
  compareError,
  followups,
  pending,
  documents,
  language,
  onCopy,
  onRegenerate,
  onCompare,
  onAsk,
  onFollowup,
  onOpenAnalysis,
}: TurnProps) {
  const result = turn.result;
  const files = turn.files ?? [];
  const retry = canRetry ? (
    <button type="button" className="chat-link" onClick={onRegenerate}>
      Try again
    </button>
  ) : null;
  return (
    <div className="chat-exchange">
      {files.map((f, i) => (
        <FileBanner key={`${f.name}${i}`} file={f} turn={turn} progress={progress?.[f.name]} />
      ))}
      {turn.question ? <p className="chat-q">{turn.question}</p> : null}
      {result ? (
        <>
          <div className="chat-a">
            <Answer text={result.answer} />
            <div className="chat-a__foot">
              <Verified result={result} />
              <span className="chat-a__tools">
                <button type="button" className="chat-tool" onClick={() => onCopy(turn.id, result.answer)} aria-label={copied ? "Copied" : "Copy answer"} title={copied ? "Copied" : "Copy"}>
                  <Icon name={copied ? "tick" : "copy"} size={15} />
                </button>
                {canRetry ? (
                  <button type="button" className="chat-tool" onClick={onRegenerate} aria-label="Regenerate answer" title="Regenerate">
                    <Icon name="refresh" size={15} />
                  </button>
                ) : null}
              </span>
            </div>
            {hasHow(result, turn.steps) ? <How result={result} steps={turn.steps} onOpenAnalysis={onOpenAnalysis} /> : null}
          </div>
          {result.imports?.some(inBooks) ? <Imported imports={result.imports} /> : null}
          {showCompare ? (
            <div className="chat-after">
              <button type="button" className="chat-compare" onClick={onCompare} disabled={comparing} aria-busy={comparing}>
                {comparing ? <Spinner size={14} /> : <Icon name="layers" size={16} />}
                <span>{comparing ? "Opening the report…" : "Open the full report: GST, gross profit, party ledgers"}</span>
                {comparing ? null : <Icon name="right" size={16} />}
              </button>
              {compareError ? (
                <p className="chat-after__error" role="alert">
                  {compareError}
                </p>
              ) : null}
            </div>
          ) : null}
          {pending?.length ? <PendingRegisters pending={pending} documents={documents ?? []} language={language} onReply={onFollowup} /> : null}
          {followups?.length ? (
            <div className="chat-followups" role="group" aria-label="Suggested questions">
              {followups.map((q) => (
                <button key={q} type="button" className="chat-followup" onClick={() => onFollowup(q)}>
                  {q}
                </button>
              ))}
            </div>
          ) : null}
        </>
      ) : turn.shared ? (
        last && onAsk && files.some((f) => f.datasetId !== undefined) ? (
          <div className="chat-after">
            <button type="button" className="chat-suggest" onClick={() => onAsk(files.length > 1 ? "Explain these files" : "Explain this file", files.length > 1 ? EXPLAIN_MANY : EXPLAIN_ONE)}>
              <Icon name="info" size={15} />
              {files.length > 1 ? "Explain these files" : "Explain this file"}
            </button>
          </div>
        ) : null
      ) : turn.stopped ? (
        <div className="chat-a">
          {turn.partial ? <Answer text={turn.partial} /> : null}
          <p className="chat-a__note">
            Stopped.{turn.partial ? " Figures in a stopped answer are not checked." : ""} {retry}
          </p>
        </div>
      ) : turn.error ? (
        <div className="chat-a is-error" role="alert">
          <Icon name="alert" size={16} />
          <p>
            {turn.error} {retry}
          </p>
        </div>
      ) : (
        <LiveCard turn={turn} />
      )}
    </div>
  );
});

/** The answer being written: the live step with a spinner, then the text as it arrives. */
function LiveCard({ turn }: { turn: Turn }) {
  const live = turn.live;
  const step = live?.steps.at(-1) ?? (turn.files?.length && !turn.prompt ? "Uploading…" : "Thinking…");
  const line = (
    <p className="chat-step" role="status">
      <Spinner size={16} />
      <span className="chat-step__text">{step}</span>
      {/* Hidden from screen readers: inside the status line it would be read out again every second. */}
      <span className="chat-step__time" aria-hidden="true">
        <Elapsed />
      </span>
    </p>
  );
  if (!live?.text) {
    return (
      <div className="chat-a is-typing">
        {live?.note ? <p className="chat-a__note">{live.note}</p> : null}
        {line}
        {live?.analysis ? <AnalysisView result={live.analysis} compact /> : null}
      </div>
    );
  }
  return (
    <div className="chat-a">
      {live.note ? <p className="chat-a__note">{live.note}</p> : null}
      <Answer text={live.text} streaming />
      {line}
    </div>
  );
}

type ThreadProps = {
  engine: ChatEngine;
  onOpenAnalysis?: (spec: AnalysisSpec) => void;
  /** Shared files can be explained with one tap (Home). */
  onAsk?: (question: string, prompt: string) => void;
};

/** The conversation on screen, in the design's bubbles. */
export function ChatThread({ engine, onOpenAnalysis, onAsk }: ThreadProps) {
  const { turns, sending, copied, uploading, canCompare, comparing, compareError, onCopy, onRegenerate, onFollowup, onCompare } = engine;
  const pending = sending ? undefined : turns.at(-1)?.result?.pending_registers;
  // The chips speak the language the answer asked in: the backend's pick for the message sent, which is a chip's own
  // prompt when there is one ("Explain this file" sends English), else what the person typed.
  const language = pending?.length ? answerLanguage(turns) : "hinglish";
  return (
    <div className="chat-list">
      {turns.map((turn, index) => {
        const last = index === turns.length - 1;
        return (
          <TurnView
            key={turn.id}
            turn={turn}
            last={last}
            canRetry={last && !sending}
            copied={copied === turn.id}
            progress={turn.live ? uploading : undefined}
            showCompare={last && canCompare && Boolean(turn.result)}
            comparing={last && comparing}
            compareError={last ? compareError : null}
            followups={last && !sending ? turn.followups : undefined}
            pending={last ? pending : undefined}
            documents={last && pending?.length ? engine.active?.documents : undefined}
            language={last ? language : "hinglish"}
            onCopy={onCopy}
            onRegenerate={onRegenerate}
            onCompare={onCompare}
            onAsk={onAsk && !sending ? onAsk : undefined}
            onFollowup={onFollowup}
            onOpenAnalysis={onOpenAnalysis}
          />
        );
      })}
    </div>
  );
}
