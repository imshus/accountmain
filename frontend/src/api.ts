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

// Where the backend is. In development it is empty: Vite forwards /api to the backend. A frontend
// built for another host sets VITE_API_URL; the Android app asks the user (menu → Server) and keeps
// the address on the phone.
const SERVER_KEY = "accountsai.server";

/** Running inside the Android app (no development proxy, so a server address is required). */
export const isApp = Capacitor.isNativePlatform();

function stored(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function serverUrl(): string {
  return (stored(SERVER_KEY) || import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
}

export function saveServer(url: string): void {
  localStorage.setItem(SERVER_KEY, normaliseServer(url));
}

// A computer on the local network (an IP address or localhost) rarely has HTTPS; a server with a domain name nearly always does.
const LOCAL_HOST = /^(localhost|\d{1,3}(\.\d{1,3}){3}|\[[0-9a-f:]+\])(:\d+)?$/i;

/** "192.168.1.10:8000" -> "http://192.168.1.10:8000"; "account.example.in" -> "https://account.example.in" */
export function normaliseServer(url: string): string {
  const text = url.trim().replace(/\/+$/, "");
  if (!text || /^https?:\/\//i.test(text)) return text;
  return `${LOCAL_HOST.test(text) ? "http" : "https"}://${text}`;
}

async function healthAt(base: string): Promise<Health> {
  const response = await fetch(`${base}/api/health`, { signal: AbortSignal.timeout(8000) });
  if (!response.ok) throw new Error(String(response.status));
  return (await response.json()) as Health;
}

/** Check an address before saving it: the backend must answer its health check. An http:// address that fails is
 * tried again over https://, because a server that redirects http to https blocks the app's requests at the redirect.
 * Returns the address that answered. */
export async function checkServer(url: string): Promise<{ base: string; health: Health }> {
  const base = normaliseServer(url);
  const secure = /^http:\/\//i.test(base) ? base.replace(/^http:/i, "https:") : null;
  for (const candidate of secure ? [base, secure] : [base]) {
    try {
      return { base: candidate, health: await healthAt(candidate) };
    } catch {
      // Try the next form of the address.
    }
  }
  throw new ApiError(
    0,
    `No Accounts.ai backend answered at ${base}${secure ? ` or ${secure}` : ""}. Check the address, that the backend is running, and (for a computer on your network) that the phone is on the same Wi-Fi.`,
  );
}

let httpsTried = false;

/** A saved http:// address whose server now only works over https (it redirects): switch to https once, if the backend
 * answers there, so the app keeps working without the user retyping the address. */
async function switchToHttps(): Promise<boolean> {
  const base = serverUrl();
  if (httpsTried || !stored(SERVER_KEY) || !/^http:\/\//i.test(base)) return false;
  httpsTried = true;
  const secure = base.replace(/^http:/i, "https:");
  try {
    await healthAt(secure);
  } catch {
    return false;
  }
  saveServer(secure);
  return true;
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
  if (status === 502 || status === 503 || status === 504) {
    return "The backend is not responding (it may be restarting). Try again in a moment.";
  }
  if (status >= 500) return `The backend hit an error (${status}). Try again; if it keeps happening, check the backend window.`;
  return `Request failed (${status})`;
}

function unreachable(): string {
  const base = serverUrl();
  return base ? `Cannot reach the backend at ${base}. Is it running, and is this device on the same network?` : "Cannot reach the backend. Is it running on port 8000?";
}

// Without a limit, a phone whose saved server is off (or out of Wi-Fi range) waits minutes for the OS to give up.
const TIMEOUT_MS = 20_000;
/** For requests that can rightly take longer (a whole register imported, a non-streamed AI answer). */
const NO_TIMEOUT = 0;

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
    if (!expired() && (await switchToHttps())) return request<T>(path, init, timeoutMs);
    throw new ApiError(0, expired() ? timedOut(init, timeoutMs) : unreachable());
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
    if (await switchToHttps()) return streamChat(path, payload, onEvent, options);
    throw new ApiError(0, unreachable());
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

function putJson<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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
  /** The main chat: questions about the files shared in the conversation (or general questions without files). */
  filesChatStream: (datasetIds: number[], messages: ChatMessage[], provider: ProviderId, onEvent: (event: ChatEvent) => void, options?: StreamOptions) =>
    streamChat("/api/chat/stream", { messages, provider, dataset_ids: datasetIds }, onEvent, options),
  documents: (datasetIds: number[]) => postJson<DocumentInfo[]>("/api/documents", { dataset_ids: datasetIds }),
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
    xhr.onerror = () => reject(new ApiError(0, unreachable()));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
