import type { DragEvent } from "react";
import { formatCount } from "../../format";
import type { ChatMessage, ChatResult, DatasetDetail, DocumentInfo } from "../../types";
import type { SharedFile, Turn } from "./chatStore";

export const ACCEPTED = [".xlsx", ".xlsm", ".xls", ".csv"];
export const MAX_FILES = 6;

export const EXPLAIN_ONE = "Explain the file I just shared.";
export const EXPLAIN_MANY = "Explain the files I just shared: which is which, and what each contains.";
export const COMPARE_PROMPT =
  "Explain the files I just shared (which is the sales register and which is the purchase register), then analyse " +
  "the two together: sales vs purchases, margin, GST payable after input tax credit, month by month, items, and anything I should check.";

export const isAccepted = (file: File) => ACCEPTED.some((ext) => file.name.toLowerCase().endsWith(ext));

export type ReplyLanguage = "english" | "hinglish" | "hindi";

/** Words only Hinglish uses, as the backend lists them (llm/common.py); not "me", "to" or "so", which English has too. */
const HINGLISH = new Set(
  ("kya kitna kitni kitne hai hain aur ka ki ke ko mein batao dikhao sabse kaun kis kaunsa dono wala wali hua hui " +
    "iska uska inka unka nahi").split(" "),
);

/**
 * The language the backend answers a message in (its reply_language): Devanagari is Hindi, a Hinglish word makes it
 * Hinglish, any other Latin word English; null without such letters (the message before it decides).
 */
export function replyLanguage(text: string): ReplyLanguage | null {
  if (/[ऀ-ॣॱ-ॿ]/.test(text)) return "hindi";
  const words = text.toLowerCase().match(/[a-z]+/g) ?? [];
  if (words.some((w) => HINGLISH.has(w))) return "hinglish";
  return words.length ? "english" : null;
}

/** The language of the latest answer: that of the latest message sent with one (a chip's prompt included), else Hinglish. */
export function answerLanguage(turns: Turn[]): ReplyLanguage {
  for (let i = turns.length - 1; i >= 0; i--) {
    const language = turns[i].result ? replyLanguage(turns[i].prompt ?? turns[i].question) : null;
    if (language) return language;
  }
  return "hinglish";
}

/**
 * What a "Sales" / "Purchase" chip sends, as the person would type it in the conversation's language: "Yeh sales data
 * hai", "This is sales data" or "यह सेल्स डेटा है"; ``name`` (the sheet's file) leads when the conversation has others.
 */
export function registerReply(register: "sales" | "purchases", name: string | null, language: ReplyLanguage): string {
  const kind = register === "sales" ? "sales" : "purchase";
  if (language === "english") return name ? `${name} is ${kind} data` : `This is ${kind} data`;
  if (language === "hindi") {
    const hindi = register === "sales" ? "सेल्स" : "परचेज़";
    return name ? `${name} ${hindi} डेटा है` : `यह ${hindi} डेटा है`;
  }
  return name ? `${name} ${kind} data hai` : `Yeh ${kind} data hai`;
}

/** The backend's longest message (characters). */
const MESSAGE_MAX = 20_000;

/**
 * Earlier answered turns as plain messages, so follow-up questions keep their context. An answer that would pass the
 * backend's limit with its context block goes without it, and a longer answer is cut to the limit.
 */
export function historyOf(turns: Turn[]): ChatMessage[] {
  return turns.flatMap((turn) => {
    if (!turn.result) return [];
    const answer = turn.result.answer;
    const block = contextBlock(turn.result);
    return [
      { role: "user" as const, content: turn.prompt ?? turn.question },
      {
        role: "assistant" as const,
        content: block && answer.length + 2 + block.length <= MESSAGE_MAX ? `${answer}\n\n${block}` : cut(answer, MESSAGE_MAX),
      },
    ];
  });
}

/** Longest line of a context block, and longest block (between the tags). */
const CONTEXT_LINE_MAX = 600;
const CONTEXT_MAX = 2000;

/** The first ``max`` characters of ``text``, one fewer when the last would be half of a surrogate pair (an emoji). */
function cut(text: string, max: number): string {
  if (text.length <= max) return text;
  const code = text.charCodeAt(max - 1);
  return text.slice(0, code >= 0xd800 && code <= 0xdbff ? max - 1 : max);
}

/** An expression on one line, so each tool call stays one line of the block. */
const oneLine = (text: string) => String(text).replace(/\s*[\r\n]+\s*/g, " ");

/** A spec without the keys that say nothing (null, "", false, []), in its filters, measures and group_by too. */
function shortSpec(this: unknown, _key: string, value: unknown): unknown {
  if (Array.isArray(this)) return value;
  return value === null || value === "" || value === false || (Array.isArray(value) && !value.length) ? undefined : value;
}

/**
 * The tool calls behind an answer, sent back with it as history so a follow-up ("and for March?") can reuse the same
 * table, filters and SQL: analyses, SQL queries, calculations, then formula checks, one per line; failed calls are
 * left out. "" when none succeeded. The backend reads this exact format (chat endpoints and /api/chat/followups).
 */
export function contextBlock(result: ChatResult): string {
  const lines = [
    ...(result.analyses ?? []).filter((a) => !a.error && a.spec).map((a) => `analyse ${JSON.stringify(a.spec, shortSpec)}`),
    // Only line breaks go: runs of spaces may be inside a string literal ('satyam  jewellers').
    ...result.queries.filter((q) => !q.error && q.sql).map((q) => `run_sql ${oneLine(String(q.sql)).trim()}`),
    ...(result.calculations ?? []).filter((c) => !c.error).map((c) => `calculate ${oneLine(c.expression)}`),
    ...(result.formula_checks ?? []).filter((c) => !c.error).map((c) => `check_formula ${oneLine(c.target)} = ${oneLine(c.expression)}`),
  ].map((line) => (line.length > CONTEXT_LINE_MAX ? `${cut(line, CONTEXT_LINE_MAX - 1)}…` : line));
  if (!lines.length) return "";
  if (lines.join("\n").length > CONTEXT_MAX) {
    // Whole lines go from the end, and a last "…" says some were left out.
    while (lines.length && [...lines, "…"].join("\n").length > CONTEXT_MAX) lines.pop();
    lines.push("…");
  }
  return `<context>\n${lines.join("\n")}\n</context>`;
}

/** Give the turn's file cards the dataset ids of the files that uploaded (matched by name and size). */
export function linkCards(cards: SharedFile[] | undefined, done: { file: File; detail: DatasetDetail }[]): SharedFile[] {
  const left = [...done];
  return (cards ?? []).map((card) => {
    if (card.datasetId !== undefined) return card;
    const i = left.findIndex((d) => d.file.name === card.name && d.file.size === card.size);
    if (i < 0) return card;
    const [hit] = left.splice(i, 1);
    return { ...card, datasetId: hit.detail.id };
  });
}

/** The labels the backend detected for each uploaded card ("Sales register"). */
export function labelCards(cards: SharedFile[] | undefined, documents: DocumentInfo[]): SharedFile[] {
  return (cards ?? []).map((f) =>
    f.datasetId === undefined ? f : { ...f, kinds: [...new Set(documents.filter((d) => d.dataset_id === f.datasetId).map((d) => d.label))] },
  );
}

/** What a screen reader hears when an answer is ready. */
export function readyText(result: ChatResult): string {
  const check = result.verification;
  if (check.status === "verified") return `Answer ready. ${check.figures} figure${check.figures === 1 ? "" : "s"} checked against your data.`;
  if (check.status === "unverified") return `Answer ready. Check ${check.unverified.join(", ")}.`;
  return "Answer ready.";
}

/**
 * One line per thing the AI did, as the live steps said it ("Analysed: Total Taxable Value by Customer"); the
 * reported steps when the work was done on the server (the sales + purchases comparison); then the figure check.
 */
export function workLines(result: ChatResult, steps: string[] = []): string[] {
  const work = [
    ...(result.analyses ?? []).map((a) => (a.error ? `Analysis failed: ${a.error}` : `Analysed: ${a.description}`)),
    ...(result.formula_checks ?? []).map((c) =>
      c.error ? `Check failed: ${c.target} = ${c.expression}` : `Checked ${c.target} = ${c.expression} on ${formatCount(c.matches ?? 0)}/${formatCount(c.rows_checked ?? 0)} rows`,
    ),
    ...(result.calculations ?? []).map((c) => `Calculated ${c.expression} = ${c.error ?? c.result}`),
    ...result.queries.map((q) => (q.error ? "A query failed" : `Ran a query (${formatCount(q.row_count)} row${q.row_count === 1 ? "" : "s"})`)),
  ];
  const lines = work.length ? work : [...steps];
  const check = result.verification;
  if (check.status === "verified" && check.figures) {
    lines.push(`Checked ${formatCount(check.figures)} figure${check.figures === 1 ? "" : "s"} against your data${check.corrected ? " (one corrected automatically)" : ""}`);
  } else if (check.status === "unverified") {
    lines.push(`Not found in your data: ${check.unverified.join(", ")}`);
  }
  return lines;
}

export function hasWork(result: ChatResult): boolean {
  return (result.analyses?.length ?? 0) + result.queries.length + (result.calculations?.length ?? 0) + (result.formula_checks?.length ?? 0) > 0;
}

/** Whether "how this was calculated" has anything to show. */
export function hasHow(result: ChatResult, steps: string[] = []): boolean {
  return hasWork(result) || steps.length > 0 || result.verification.status !== "no_figures";
}

/** Only file drags show the drop overlay; dragging selected text does not. */
export function hasFiles(event: DragEvent | globalThis.DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

export async function copyText(text: string): Promise<void> {
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

/** "Today", "Yesterday" or "23 Oct 2026", for a time in milliseconds. */
export function dayLabel(time: number, now = new Date()): string {
  const day = new Date(time);
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((start(now) - start(day)) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(day);
}

export function timeLabel(time: number): string {
  return new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" }).format(new Date(time));
}
