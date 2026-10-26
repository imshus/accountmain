import type {
  AccountsMeta,
  AnalysisResult,
  AnalysisSpec,
  AnalysisTable,
  BookDetail,
  BookSummary,
  Company,
  ImportResult,
  Ledger,
  Metal,
  RegisterType,
  VoucherDetail,
  VoucherRow,
  ChatEvent,
  ChatMessage,
  DocumentInfo,
  ChatResult,
  ColumnCalcResult,
  DatasetDetail,
  DatasetSummary,
  FollowupsRequest,
  FollowupsResponse,
  GstNet,
  Health,
  ProviderId,
  QueryResult,
  Report,
  RowsPage,
  Setup,
  Sheet,
} from "./types";

import { Capacitor } from "@capacitor/core";

// Where the backend is: VITE_API_URL in frontend/.env, built into the app (build-apk.bat checks it). Nothing else sets
// it; the app has no address field. `npm run dev` ignores it and calls /api, which Vite forwards to BACKEND_URL, so
// development never writes into the books on the real server.
const CONFIGURED = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/+$/, "");
// Without http(s):// the WebView would fetch "account.example.in/api/..." from the app itself, so treat it as missing.
const API_URL = import.meta.env.DEV || !/^https?:\/\/[^\s/]+/i.test(CONFIGURED) ? "" : CONFIGURED;

/** Running inside the Android app (no development proxy, so the build must carry VITE_API_URL). */
export const isApp = Capacitor.isNativePlatform();

export function serverUrl(): string {
  return API_URL;
}

// Earlier versions kept a typed-in address on the phone; it is no longer read, so drop it.
try {
  localStorage.removeItem("accountsai.server");
} catch {
  // Storage blocked: nothing to drop.
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  if (status === 413) return "This file is larger than the server accepts. Raise the upload limit on the server (nginx: client_max_body_size).";
  if (status === 502 || status === 503 || status === 504) {
    return "The backend is not responding (it may be restarting). Try again in a moment.";
  }
  if (status >= 500) return `The backend hit an error (${status}). Try again; if it keeps happening, check the backend window.`;
  return `Request failed (${status})`;
}

function unreachable(): string {
  const base = serverUrl();
  return base
    ? `Cannot reach the backend at ${base}. Check that this device can reach it (for a PC on your network, be on the same Wi-Fi) and that the server is running.`
    : "Cannot reach the backend. Is it running on port 8000?";
}

const CRASHED =
  "The server is running but failed on this request without saying why (a server error). Try again; if it keeps happening, the reason is in the server's log (pm2 logs backend-app).";

/** A request that got no readable answer. If the server still answers its health check, it did reply, but without
 * CORS headers, which is how a crash on the server (or a web-server error page) looks from the app. */
async function whyNoAnswer(): Promise<{ up: boolean; message: string }> {
  try {
    const response = await fetch(`${serverUrl()}/api/health`, { signal: AbortSignal.timeout(5000) });
    if (response.ok) return { up: true, message: CRASHED };
  } catch {
    // Really out of reach.
  }
  return { up: false, message: unreachable() };
}

// Without a limit, a phone whose server is off or out of reach waits minutes for the OS to give up.
const TIMEOUT_MS = 20_000;
/** For requests that can rightly take longer (a whole register imported, a non-streamed AI answer). */
const NO_TIMEOUT = 0;
/** Suggested questions are optional: not worth a long wait. */
const FOLLOWUPS_TIMEOUT_MS = 15_000;
/** Chat copies go up and down in the background and can be large (up to 2 MB each, a scope holds up to 30). */
const CHATS_TIMEOUT_MS = 60_000;

function timedOut(init: RequestInit | undefined, ms: number): string {
  const seconds = Math.round(ms / 1000);
  const method = (init?.method ?? "GET").toUpperCase();
  return method === "GET"
    ? `The server did not answer within ${seconds} seconds. Check that the backend is running and this device can reach it, then try again.`
    : `The server did not answer within ${seconds} seconds, so this change may or may not have been saved. Check (for an entry, look in the Entries list) before trying again.`;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs: number = TIMEOUT_MS): Promise<T> {
  const signal = init?.signal ?? (timeoutMs && typeof AbortSignal.timeout === "function" ? AbortSignal.timeout(timeoutMs) : undefined);
  const expired = () => Boolean(timeoutMs && !init?.signal && signal?.aborted);
  let response: Response;
  try {
    response = await fetch(serverUrl() + path, { ...init, signal });
  } catch {
    throw new ApiError(0, expired() ? timedOut(init, timeoutMs) : (await whyNoAnswer()).message);
  }
  let body: unknown = null;
  if (response.status !== 204) {
    try {
      body = await response.json();
    } catch {
      // The time can also run out while the answer is still arriving: never hand back an empty answer then.
      if (expired()) throw new ApiError(0, timedOut(init, timeoutMs));
    }
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, body));
  return body as T;
}

/** POST a chat and follow its server-sent events: steps and answer text arrive as they happen. */
export type StreamOptions = { fresh?: boolean; signal?: AbortSignal };

async function streamChat(path: string, payload: object, onEvent: (event: ChatEvent) => void, options: StreamOptions = {}): Promise<ChatResult> {
  let response: Response;
  try {
    response = await fetch(serverUrl() + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ ...payload, fresh: options.fresh ?? false }),
      signal: options.signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError(0, (await whyNoAnswer()).message);
  }
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, errorMessage(response.status, body));
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const data = chunk.split("\n").filter((line) => line.startsWith("data: ")).map((line) => line.slice(6)).join("\n");
      if (!data) continue;
      const event = JSON.parse(data) as ChatEvent;
      if (event.type === "done") return event.result;
      if (event.type === "error") throw new ApiError(event.status, event.message);
      onEvent(event);
    }
  }
  throw new ApiError(0, "The answer stopped before it finished. Try again.");
}

function postJson<T>(path: string, payload: unknown, timeoutMs: number = TIMEOUT_MS): Promise<T> {
  return request<T>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    timeoutMs,
  );
}

function putJson<T>(path: string, payload: unknown, timeoutMs: number = TIMEOUT_MS): Promise<T> {
  return request<T>(
    path,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    timeoutMs,
  );
}

export const api = {
  health: () => request<Health>("/api/health"),
  datasets: () => request<DatasetSummary[]>("/api/datasets"),
  dataset: (id: number) => request<DatasetDetail>(`/api/datasets/${id}`),
  deleteDataset: (id: number) => request<null>(`/api/datasets/${id}`, { method: "DELETE" }),
  runSql: (id: number, sql: string) => postJson<QueryResult>(`/api/datasets/${id}/sql`, { sql }),
  chatStream: (id: number, messages: ChatMessage[], provider: ProviderId, onEvent: (event: ChatEvent) => void, options?: StreamOptions) =>
    streamChat(`/api/datasets/${id}/chat/stream`, { messages, provider }, onEvent, options),
  chat: (id: number, messages: ChatMessage[], provider: ProviderId) =>
    postJson<ChatResult>(`/api/datasets/${id}/chat`, { messages, provider }, NO_TIMEOUT),
  calc: (expression: string) => postJson<{ expression: string; result: string }>("/api/calc", { expression }),
  columnCalc: (
    id: number,
    table: string,
    body: { expression: string; save_as?: string; compare_to?: string; tolerance?: number },
  ) => postJson<ColumnCalcResult>(`${sheetPath(id, table)}/calculate`, body),
  rows: (id: number, table: string, offset: number, limit: number, search: string) =>
    request<RowsPage>(
      `${sheetPath(id, table)}/rows?${new URLSearchParams({ offset: String(offset), limit: String(limit), ...(search ? { search } : {}) })}`,
    ),
  addRow: (id: number, table: string, values: Record<string, string>) =>
    postJson<Sheet>(`${sheetPath(id, table)}/rows`, { values }),
  deleteRow: (id: number, table: string, rowid: number) =>
    request<Sheet>(`${sheetPath(id, table)}/rows/${rowid}`, { method: "DELETE" }),
  saveNotes: (id: number, table: string, notes: string) =>
    request<Sheet>(`${sheetPath(id, table)}/notes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    }),
  setup: (id: number, table: string) => request<Setup>(`${sheetPath(id, table)}/setup`),
  saveSetup: (id: number, table: string, body: { mapping?: Record<string, string>; classification?: Record<string, string> }) =>
    request<Setup>(`${sheetPath(id, table)}/setup`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  report: (id: number, table: string, kind: string, params: Record<string, string>) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== ""));
    return request<Report>(`${sheetPath(id, table)}/reports/${kind}?${query}`);
  },
  books: () => request<BookSummary[]>("/api/books"),
  book: (id: number) => request<BookDetail>(`/api/books/${id}`),
  createBook: (body: { name: string; sales: number[]; purchases: number[]; mixed?: number[] }) =>
    postJson<BookDetail>("/api/books", body),
  setBookSheets: (id: number, registers: Record<string, RegisterType>) =>
    request<BookDetail>(`/api/books/${id}/sheets`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ registers }),
    }),
  deleteBook: (id: number) => request<null>(`/api/books/${id}`, { method: "DELETE" }),
  bookReport: (id: number, kind: string, params: Record<string, string>) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== ""));
    return request<Report>(`/api/books/${id}/reports/${kind}?${query}`);
  },
  /** The main chat: questions about the files shared in the conversation (or general questions without files). With a
   * company the AI can also add a shared sales or purchase sheet to its books (the result's `imports`). */
  filesChatStream: (
    datasetIds: number[],
    companyId: number | null,
    messages: ChatMessage[],
    provider: ProviderId,
    onEvent: (event: ChatEvent) => void,
    options?: StreamOptions,
  ) => streamChat("/api/chat/stream", { messages, provider, dataset_ids: datasetIds, company_id: companyId }, onEvent, options),
  documents: (datasetIds: number[]) => postJson<DocumentInfo[]>("/api/documents", { dataset_ids: datasetIds }),
  /** Up to three questions worth asking next, for the conversation ending with an answer. */
  followups: (body: FollowupsRequest) => postJson<FollowupsResponse>("/api/chat/followups", body, FOLLOWUPS_TIMEOUT_MS),
  /** The server's copy of one scope's AI chats ("home", "ds-2", "book-1"), and the ones deleted on any device. */
  chats: (scope: string) => request<{ chats: unknown[]; deleted: unknown[] }>(`/api/chats?${new URLSearchParams({ scope })}`, undefined, CHATS_TIMEOUT_MS),
  /** Keep a conversation on the server; it answers with the copy it kept (a newer one from another device wins), or
   * chat null with the delete that won. */
  putChat: (scope: string, chat: { id: string }) =>
    putJson<{ chat: unknown; deleted?: unknown }>(`/api/chats/${encodeURIComponent(scope)}/${encodeURIComponent(chat.id)}`, chat, CHATS_TIMEOUT_MS),
  deleteChat: (scope: string, id: string, updated: number) =>
    request<null>(`/api/chats/${encodeURIComponent(scope)}/${encodeURIComponent(id)}?${new URLSearchParams({ updated: String(updated) })}`, {
      method: "DELETE",
    }),
  bookChatStream: (id: number, messages: ChatMessage[], provider: ProviderId, onEvent: (event: ChatEvent) => void, options?: StreamOptions) =>
    streamChat(`/api/books/${id}/chat/stream`, { messages, provider }, onEvent, options),
  bookChat: (id: number, messages: ChatMessage[], provider: ProviderId) =>
    postJson<ChatResult>(`/api/books/${id}/chat`, { messages, provider }, NO_TIMEOUT),
  bookSql: (id: number, sql: string) => postJson<QueryResult>(`/api/books/${id}/sql`, { sql }),
  /** Open the backend's connection to the AI while the question is being typed (free, no tokens). */
  warmAi: () => request<null>("/api/ai/warm", { method: "POST" }).catch(() => null),
  datasetFields: (id: number) => request<AnalysisTable[]>(`/api/datasets/${id}/fields`),
  analyseDataset: (id: number, spec: AnalysisSpec) => postJson<AnalysisResult>(`/api/datasets/${id}/analyse`, spec),
  bookFields: (id: number) => request<AnalysisTable[]>(`/api/books/${id}/fields`),
  analyseBook: (id: number, spec: AnalysisSpec) => postJson<AnalysisResult>(`/api/books/${id}/analyse`, spec),
  // Double-entry books
  accountsMeta: () => request<AccountsMeta>("/api/accounts/meta"),
  companies: () => request<Company[]>("/api/companies"),
  createCompany: (body: { name: string; gstin?: string; fy_start?: string }) => postJson<Company>("/api/companies", body),
  updateCompany: (id: number, body: { name?: string; gstin?: string; locked_until?: string | null; fy_start?: string }) =>
    putJson<Company>(`/api/companies/${id}`, body),
  ledgers: (id: number) => request<Ledger[]>(`/api/companies/${id}/ledgers`),
  saveLedger: (
    id: number,
    ledgerId: number | null,
    body: {
      name: string;
      group: string;
      opening: string;
      gstin?: string;
      state_code?: string | null;
      credit_days?: number | null;
      opening_gold?: string;
      opening_silver?: string;
    },
  ) =>
    ledgerId ? putJson<Ledger>(`/api/companies/${id}/ledgers/${ledgerId}`, body) : postJson<Ledger>(`/api/companies/${id}/ledgers`, body),
  vouchers: (id: number, params: Record<string, string>) =>
    request<{ total: number; rows: VoucherRow[] }>(`/api/companies/${id}/vouchers?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== ""))}`),
  voucher: (id: number, voucherId: number) => request<VoucherDetail>(`/api/companies/${id}/vouchers/${voucherId}`),
  createVoucher: (id: number, body: unknown) => postJson<VoucherDetail>(`/api/companies/${id}/vouchers`, body),
  createInvoice: (id: number, body: unknown) => postJson<VoucherDetail>(`/api/companies/${id}/vouchers/invoice`, body),
  createSettlement: (id: number, body: unknown) => postJson<VoucherDetail>(`/api/companies/${id}/vouchers/settlement`, body),
  createJewellery: (id: number, body: unknown) => postJson<VoucherDetail>(`/api/companies/${id}/vouchers/jewellery`, body),
  createMetalMove: (id: number, body: unknown) => postJson<VoucherDetail>(`/api/companies/${id}/vouchers/metal`, body),
  createRateCut: (id: number, body: unknown) => postJson<VoucherDetail>(`/api/companies/${id}/vouchers/rate-cut`, body),
  metalBalance: (id: number, partyId: number) => request<Partial<Record<Metal, number>>>(`/api/companies/${id}/metal-balance/${partyId}`),
  cancelVoucher: (id: number, voucherId: number) => request<null>(`/api/companies/${id}/vouchers/${voucherId}`, { method: "DELETE" }),
  pendingBills: (id: number, partyId: number) =>
    request<{ bill_ref: string; pending: number; bill_date: string | null }[]>(`/api/companies/${id}/bills/${partyId}`),
  importBook: (id: number, bookId: number) => postJson<ImportResult>(`/api/companies/${id}/import/book`, { book_id: bookId }, NO_TIMEOUT),
  importRegister: (id: number, datasetId: number, table: string, register: "sales" | "purchases") =>
    postJson<ImportResult>(`/api/companies/${id}/import/register`, { dataset_id: datasetId, table_name: table, register_type: register }, NO_TIMEOUT),
  importBank: (id: number, datasetId: number, table: string, bankLedgerId: number) =>
    postJson<ImportResult>(`/api/companies/${id}/import/bank`, { dataset_id: datasetId, table_name: table, bank_ledger_id: bankLedgerId }, NO_TIMEOUT),
  companyReport: (id: number, kind: string, params: Record<string, string>) =>
    request<Report>(`/api/companies/${id}/reports/${kind}?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== ""))}`),
  audit: (id: number) =>
    request<{ id: number; at: string; action: string; entity: string; entity_id: number | null; before_json: string | null; after_json: string | null }[]>(
      `/api/companies/${id}/audit`,
    ),
  gstNet: (id: number, sales: string, purchases: string) =>
    request<GstNet>(`/api/datasets/${id}/gst-net?${new URLSearchParams({ sales, ...(purchases ? { purchases } : {}) })}`),
};

function sheetPath(id: number, table: string): string {
  return `/api/datasets/${id}/sheets/${encodeURIComponent(table)}`;
}

/** Upload with XMLHttpRequest because fetch cannot report upload progress. */
export function uploadFile(file: File, onProgress: (fraction: number) => void, signal?: AbortSignal): Promise<DatasetDetail> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    signal?.addEventListener("abort", () => {
      xhr.abort();
      reject(new DOMException("Upload stopped", "AbortError"));
    });
    xhr.open("POST", `${serverUrl()}/api/upload`);
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as DatasetDetail);
      else reject(new ApiError(xhr.status, errorMessage(xhr.status, xhr.response)));
    };
    // A web server that refuses a large file (nginx answers 413 without CORS headers) also lands here.
    xhr.onerror = () =>
      void whyNoAnswer().then(({ up, message }) =>
        reject(
          new ApiError(
            0,
            up && file.size > 1024 * 1024
              ? `The server is running but refused this ${(file.size / (1024 * 1024)).toFixed(1)} MB file: most likely its upload limit (nginx: client_max_body_size 30m), otherwise a server error (see pm2 logs backend-app).`
              : message,
          ),
        ),
      );
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
