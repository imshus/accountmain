import { useCallback, useSyncExternalStore } from "react";
import { api } from "../../api";
import type { AnalysisResult, ChatImport, ChatResult, DocumentInfo, PendingRegister, QueryResult } from "../../types";
import { createChatSync } from "./chatSync";

/**
 * The AI conversations kept on this device, one list per scope ("home", "ds-2", "book-1"). A small external store,
 * so Home, History and the per-file chats all read and change the same lists, and a chat deleted in History is not
 * written back by Home a moment later. The server keeps a copy of every list (chatSync.ts).
 */

export type SharedFile = {
  name: string;
  size: number;
  datasetId?: number;
  /** What the backend detected in it, e.g. ["Sales register"]. */
  kinds?: string[];
};

export type LiveState = { steps: string[]; text: string; note?: string; analysis?: AnalysisResult };

export type Turn = {
  id: number;
  /** What the person typed ("" for files shared on their own, or the automatic sales + purchases analysis). */
  question: string;
  /** What was sent when it differs from what is shown (e.g. "Explain the file I just shared."). */
  prompt?: string;
  files?: SharedFile[];
  /** Files shared without a question: the turn is complete once they are uploaded. */
  shared?: boolean;
  result?: ChatResult;
  /** The steps the AI reported while answering (shown in "how this was calculated"). */
  steps?: string[];
  error?: string;
  stopped?: boolean;
  /** Text written before the person pressed stop. */
  partial?: string;
  /** While the upload or the answer is in progress. */
  live?: LiveState;
  /** Questions worth asking next, suggested after the answer (shown under the latest answer only). */
  followups?: string[];
};

export type Conversation = {
  id: string;
  title: string;
  updated: number;
  datasetIds: number[];
  documents: DocumentInfo[];
  turns: Turn[];
  /** Read back cut down (older turns or query rows dropped to fit this device's storage): never sent as it is. */
  trimmed?: boolean;
};

const MAX_CHATS = 30;
const MAX_TURNS = 40;
const MAX_ROWS = 50;
/** Sheets an answer asks "sales or purchase?" about that get chips (ChatThread.tsx). */
export const MAX_PENDING = 3;
/** Characters of JSON kept per scope; every scope shares the browser's ~5M-character quota. */
const STORE_BUDGET = 1_500_000;
const STORE_PREFIX = "accountsai.chats.";

const NO_CHECK: ChatResult["verification"] = { status: "no_figures", figures: 0, unverified: [], corrected: false };

const list = <T,>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : []);

/** At most three different non-empty suggested questions; undefined when there are none. */
export function cleanFollowups(value: unknown): string[] | undefined {
  const kept = [...new Set(list<unknown>(value).filter((s): s is string => typeof s === "string").map((s) => s.trim()).filter(Boolean))].slice(0, 3);
  return kept.length ? kept : undefined;
}

function storeKey(scope: string): string {
  return `${STORE_PREFIX}${scope}`;
}

const isImport = (value: unknown): value is Partial<ChatImport> & Pick<ChatImport, "register"> =>
  Boolean(value && typeof value === "object" && ["sales", "purchases"].includes((value as ChatImport).register));

/** The sheets an answer added to the books, kept small (a few problems each); undefined when there are none. */
function cleanImports(value: unknown): ChatImport[] | undefined {
  const kept = list<unknown>(value)
    .filter(isImport)
    .slice(0, 12)
    .map((i) => ({
      register: i.register,
      dataset_id: Number(i.dataset_id) || 0,
      table: String(i.table ?? ""),
      filename: String(i.filename ?? ""),
      sheet: String(i.sheet ?? ""),
      created: Number(i.created) || 0,
      skipped: Number(i.skipped) || 0,
      problems: list<unknown>(i.problems).filter((p): p is string => typeof p === "string").slice(0, 3).map((p) => p.slice(0, 300)),
    }));
  return kept.length ? kept : undefined;
}

/** The sheets an answer asks about (sales or purchases?), as many as get chips; undefined when there are none. */
function cleanPending(value: unknown): PendingRegister[] | undefined {
  const kept = list<unknown>(value)
    .filter((p): p is Partial<PendingRegister> => Boolean(p && typeof p === "object"))
    .slice(0, MAX_PENDING)
    .map((p) => ({
      dataset_id: Number(p.dataset_id) || 0,
      table: String(p.table ?? ""),
      filename: String(p.filename ?? ""),
      sheet: String(p.sheet ?? ""),
      suggestion: p.suggestion === "sales" || p.suggestion === "purchases" ? p.suggestion : null,
    }));
  return kept.length ? kept : undefined;
}

/** A stored answer made safe to show: a failed analysis has no rows, and older records may lack fields. */
function cleanResult(result: ChatResult, rows: number): ChatResult {
  const check = result.verification && typeof result.verification === "object" ? result.verification : NO_CHECK;
  return {
    ...result,
    imports: cleanImports(result.imports),
    pending_registers: cleanPending(result.pending_registers),
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
      .filter((t) => t && typeof t === "object" && (t.result || t.error || t.stopped || t.shared))
      .slice(-Math.max(1, turns))
      .map(({ live: _live, ...t }, i, kept) => ({
        ...t,
        question: typeof t.question === "string" ? t.question : "",
        files: list<SharedFile>(t.files),
        steps: list<string>(t.steps).filter((x) => typeof x === "string"),
        result: t.result ? cleanResult(t.result, rows) : undefined,
        // Suggestions show under the latest answer only, so earlier turns' are not kept.
        followups: i === kept.length - 1 ? cleanFollowups(t.followups) : undefined,
      })),
  };
}

/**
 * The chats as JSON within ``budget`` characters: query and analysis rows go first, then the oldest turns,
 * then the oldest chats. A record that cannot be serialised is skipped, so it never blocks the others. A chat
 * cut down is marked ``trimmed``, so that the server's whole copy is not overwritten with it (chatSync.ts).
 */
export function serializeChats(chats: Conversation[], budget = STORE_BUDGET): string {
  /** Each chat's JSON as the server keeps it, from the first pack (all of its rows and turns). */
  const whole = new Map<Conversation, string>();
  const pack = (rows: number, turns: number) => {
    const parts: { updated: number; json: string }[] = [];
    for (const chat of chats.slice(0, MAX_CHATS)) {
      try {
        const slim = slimChat(chat, rows, turns);
        if (!slim.turns.length) continue;
        const json = JSON.stringify(slim);
        if (!whole.has(chat)) whole.set(chat, json);
        parts.push({ updated: slim.updated, json: chat.trimmed || json !== whole.get(chat) ? JSON.stringify({ ...slim, trimmed: true }) : json });
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
  // A chat too big to be kept even on its own goes first (it stays on the server), so it cannot push out all the others.
  parts = parts.filter((p) => p.json.length + 2 <= budget);
  while (parts.length && size(parts) > budget) {
    let oldest = 0;
    parts.forEach((p, i) => {
      if (p.updated < parts[oldest].updated) oldest = i;
    });
    parts.splice(oldest, 1);
  }
  return `[${parts.map((p) => p.json).join(",")}]`;
}

function readStored(scope: string): Conversation[] {
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
      const chat = slimChat(raw, Infinity, Infinity);
      out.push(raw.trimmed === true ? { ...chat, trimmed: true } : chat);
    } catch {
      // Skip a malformed record.
    }
  }
  return out;
}

/** The JSON last written per key, so an unchanged list is not written again. */
const lastSaved = new Map<string, string>();

/** False when nothing could be written (quota reached or storage blocked), even after shrinking the history. */
function writeStored(scope: string, chats: Conversation[]): boolean {
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

// ── the store ──────────────────────────────────────────────────────────────────────────────────

const loaded = new Map<string, Conversation[]>();
const listeners = new Map<string, Set<() => void>>();
/** A forgotten scope's list (forgetChats). */
const EMPTY: Conversation[] = [];

const sync = createChatSync(
  { list: api.chats, put: api.putChat, remove: api.deleteChat, up: () => api.health().then(() => true, () => false) },
  { get: getChats, replace: replaceChats, shape: (chat) => slimChat(chat, MAX_ROWS, MAX_TURNS), scopes: storedScopes, max: MAX_CHATS },
);

/** The session's state, for the copies on the server: they are read and sent only while it is ready. */
export const syncChats = sync.session;

export function getChats(scope: string): Conversation[] {
  let chats = loaded.get(scope);
  if (!chats) {
    chats = readStored(scope);
    loaded.set(scope, chats);
    sync.opened(scope);
  }
  return chats;
}

function emit(scope: string) {
  listeners.get(scope)?.forEach((listener) => listener());
}

const isStreaming = (chats: Conversation[]) => chats.some((c) => c.turns.some((t) => t.live));

/**
 * Every conversation ``change`` touched gets a later ``updated`` than it had, whether or not the change set one: the
 * server keeps whichever copy is newer, and a copy from a device whose clock runs ahead must not win over this edit.
 * One the change set no time for (suggestions, a deleted upload taken out) moves on by 1 ms only, so it keeps its
 * place and day in History.
 */
function touch(before: Conversation[], next: Conversation[]): Conversation[] {
  const was = new Map(before.map((c) => [c.id, c]));
  return next.map((chat) => {
    const old = was.get(chat.id);
    return old && old !== chat && chat.updated <= old.updated ? { ...chat, updated: old.updated + 1 } : chat;
  });
}

/**
 * Change a scope's chats. They are written to the device whenever nothing is in progress (a turn settled, a chat
 * was created or deleted), not on every streamed token, and sent to the server a moment later. Returns false when
 * the write failed.
 */
export function updateChats(scope: string, change: (chats: Conversation[]) => Conversation[]): boolean {
  const before = getChats(scope);
  const next = touch(before, change(before));
  loaded.set(scope, next);
  emit(scope);
  sync.changed(scope, before, next);
  return isStreaming(next) ? true : writeStored(scope, next);
}

/** The server's copies merged in: shown and written like a change, but not sent back. */
function replaceChats(scope: string, chats: Conversation[]): void {
  loaded.set(scope, chats);
  emit(scope);
  writeStored(scope, chats);
}

export function deleteChat(scope: string, id: string): boolean {
  return updateChats(scope, (chats) => chats.filter((c) => c.id !== id));
}

/** The chats of a scope, newest first as kept; re-renders when they change. */
export function useChats(scope: string): Conversation[] {
  const subscribe = useCallback(
    (listener: () => void) => {
      const set = listeners.get(scope) ?? new Set();
      set.add(listener);
      listeners.set(scope, set);
      return () => set.delete(listener);
    },
    [scope],
  );
  return useSyncExternalStore(subscribe, () => loaded.get(scope) ?? getChats(scope), () => EMPTY);
}

/** The scopes with conversations on this device (not the ones forgotten since the app started). */
function storedScopes(): string[] {
  const scopes = new Set(loaded.keys());
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(STORE_PREFIX)) scopes.add(key.slice(STORE_PREFIX.length));
    }
  } catch {
    // Storage blocked: only the lists in memory.
  }
  return [...scopes].filter((scope) => loaded.get(scope) !== EMPTY);
}

/** Remove the conversations kept for one scope, e.g. "ds-4" or "book-2" after it is deleted, on the server too. */
export function forgetChats(scope: string): void {
  lastSaved.delete(storeKey(scope));
  if (loaded.has(scope)) {
    loaded.set(scope, EMPTY);
    emit(scope);
  }
  try {
    localStorage.removeItem(storeKey(scope));
  } catch {
    // Storage blocked: nothing was kept anyway.
  }
  sync.forgot(scope);
}

/** A deleted upload: drop its chat and take it out of every conversation that shared it. */
export function forgetDataset(id: number): void {
  forgetChats(`ds-${id}`);
  const uses = (c: Conversation) => c.datasetIds.includes(id) || c.documents.some((d) => d.dataset_id === id);
  for (const scope of storedScopes()) {
    if (!getChats(scope).some(uses)) continue;
    // Only the conversations that shared it change (and are sent again).
    updateChats(scope, (all) =>
      all.map((c) => (uses(c) ? { ...c, datasetIds: c.datasetIds.filter((x) => x !== id), documents: c.documents.filter((d) => d.dataset_id !== id) } : c)),
    );
  }
}

/** Start-up: remove the chats of uploads and sets that no longer exist. */
export function sweepChats(datasetIds: number[], bookIds: number[]): void {
  const datasets = new Set(datasetIds);
  const books = new Set(bookIds);
  for (const scope of storedScopes()) {
    const match = /^(ds|book)-(\d+)$/.exec(scope);
    if (match && !(match[1] === "ds" ? datasets : books).has(Number(match[2]))) forgetChats(scope);
  }
}

/** Home's conversations (History lists them). */
export const HOME_SCOPE = "home";
