import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { api, ApiError, uploadFile, type StreamOptions } from "../../api";
import type { ChatEvent, ChatMessage, ChatResult, DatasetDetail, DocumentInfo, Health, ProviderId } from "../../types";
import { cleanFollowups, getChats, updateChats, useChats, type Conversation, type LiveState, type SharedFile, type Turn } from "./chatStore";
import { COMPARE_PROMPT, historyOf, isAccepted, labelCards, linkCards, MAX_FILES, readyText, ACCEPTED, copyText } from "./chatUtils";

export type ChatStream = (
  messages: ChatMessage[],
  provider: ProviderId,
  onEvent: (event: ChatEvent) => void,
  options: StreamOptions & { datasetIds?: number[] },
) => Promise<ChatResult>;

export type Attachments = {
  onUploaded: (dataset: DatasetDetail) => void;
  /** Build a sales + purchases set from the conversation's sheets (each sheet keeps the register it was detected as).
   * Without it the chat offers no "open the full report" button. */
  onCompare?: (documents: DocumentInfo[], name: string) => Promise<void>;
};

type Options = {
  /** Where the conversations are kept on this device: "home", "ds-2", "book-1". */
  scope: string;
  health: Health | null;
  stream: ChatStream;
  /** The conversation on screen (null = a new one). */
  activeId: string | null;
  /** A conversation was started: show it (Home puts it in the address so Back returns to the start screen). */
  onStarted: (id: string) => void;
  /** Files can be shared: they are uploaded and become the conversation's data. */
  attachments?: Attachments;
  /** The composer's text box: focus moves there after a suggested question is tapped. */
  inputRef?: RefObject<HTMLTextAreaElement | null>;
};

type RunOptions = {
  prompt?: string;
  /** Files to upload first. */
  upload?: File[];
  /** Read the conversation's documents again (a retry after the upload or the documents step failed). */
  refresh?: boolean;
  /** Files shared on their own: stop after the upload unless a sales and a purchase register are now both there. */
  share?: boolean;
  fresh?: boolean;
  before: Turn[];
};

/** Delta text not yet shown: flushed to the store at most once per animation frame. */
type StreamBuffer = { turnId: number; text: string; frame: number };

/** The steps worth keeping after the answer: what was done, not "Reading the question…". */
function keptSteps(steps: string[]): string[] {
  const done = steps.map((s) => s.replace(/…$/, "")).filter((s) => !/^(Reading|Uploading|Thinking)\b/.test(s));
  return [...new Set(done)].slice(-12);
}

/** The data a scope's suggested questions are about: a file's chat ("ds-2"), a set's ("book-1"), else Home's files. */
function followupData(scope: string, datasetIds: number[]): { dataset_ids: number[]; book_id: number | null } {
  const match = /^(ds|book)-(\d+)$/.exec(scope);
  if (!match) return { dataset_ids: datasetIds, book_id: null };
  const id = Number(match[2]);
  return match[1] === "ds" ? { dataset_ids: [id], book_id: null } : { dataset_ids: [], book_id: id };
}

export const CONNECTING = "Connecting to the server…";
const NOT_SAVED = "This chat could not be saved on this device (storage is full or blocked).";
const BUSY = "Wait for the answer being written to finish, or stop it.";

/**
 * Everything the AI chat does, without its looks: conversations kept on the device, streamed answers with live
 * steps, stop, regenerate, uploads (with retry of the ones that failed), document detection and the combined
 * sales + purchases analysis. Home and the per-file chats render it their own way.
 */
export function useChatEngine({ scope, health, stream, activeId, onStarted, attachments, inputRef }: Options) {
  const chats = useChats(scope);
  const providers = health?.providers ?? [];
  // No model picker: the backend's default model (GPT-6 Luna) answers, or whichever model has a key.
  const selected = providers.find((p) => p.id === health?.default_provider && p.configured) ?? providers.find((p) => p.configured) ?? providers[0];
  const ready = selected?.configured ?? false;

  const [sendingId, setSendingId] = useState<string | null>(null);
  const [uploading, setUploading] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState<{ chatId: string; message: string } | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sendingRef = useRef(false);
  /** Files that failed to upload, by turn id, so "Try again" uploads them again. */
  const retryFiles = useRef(new Map<number, File[]>());

  const active = chats.find((c) => c.id === activeId) ?? null;
  const turns = active?.turns ?? [];
  const sending = sendingId !== null;

  // The latest render's values, for the stable callbacks handed to the memoised turns and for replies that come later.
  const latest = useRef({ regenerate, compare, ask, activeId });
  useLayoutEffect(() => {
    latest.current = { regenerate, compare, ask, activeId };
  });

  useEffect(() => {
    if (health) setNotice((current) => (current === CONNECTING ? null : current));
  }, [health]);

  // Leaving (e.g. Back from a file's chat) stops the request; the answer so far is kept as a stopped turn.
  useEffect(() => () => abortRef.current?.abort(), []);

  function update(change: (chats: Conversation[]) => Conversation[]) {
    if (!updateChats(scope, change)) setNotice(NOT_SAVED);
  }
  function updateChat(id: string, change: (c: Conversation) => Conversation) {
    update((list) => list.map((c) => (c.id === id ? change(c) : c)));
  }
  function updateTurn(chatId: string, turnId: number, change: (t: Turn) => Turn) {
    updateChat(chatId, (c) => ({ ...c, updated: Date.now(), turns: c.turns.map((t) => (t.id === turnId ? change(t) : t)) }));
  }
  const setLive = (chatId: string, turnId: number, live: LiveState) => updateTurn(chatId, turnId, (t) => ({ ...t, live }));

  /** Repeated text is still read out: alternate a trailing space. */
  function announce(text: string) {
    setAnnouncement((current) => (current === text ? `${text} ` : text));
  }

  /** Why a question cannot be sent yet, or null. */
  function blocked(): string | null {
    if (!health) return CONNECTING;
    if (!selected) return "The server has no AI model set up.";
    if (!ready) return `${selected.label} needs an API key in the backend's .env file.`;
    return null;
  }

  function startChat(title: string): string {
    const id = `c${Date.now()}`;
    update((list) => [{ id, title: title.slice(0, 60), updated: Date.now(), datasetIds: [], documents: [], turns: [] }, ...list]);
    onStarted(id);
    return id;
  }

  function addTurn(chatId: string, turn: Turn) {
    updateChat(chatId, (c) => ({ ...c, updated: Date.now(), turns: [...c.turns, turn] }));
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

  /**
   * Ask the backend for questions worth asking next, in the background, and keep them on the turn while it is still
   * the conversation's latest with this answer (not asked past, regenerated or deleted meanwhile). They are
   * optional: any failure just means no suggestions.
   */
  async function suggest(chatId: string, turnId: number, result: ChatResult, provider: ProviderId) {
    const chat = getChats(scope).find((c) => c.id === chatId);
    const index = chat?.turns.findIndex((t) => t.id === turnId) ?? -1;
    if (!chat || index < 0) return;
    // The latest messages only (whole pairs, so they still start with a question): the backend takes up to 40.
    const messages = historyOf(chat.turns.slice(0, index + 1)).slice(-40);
    const reply = await api.followups({ messages, ...followupData(scope, chat.datasetIds), provider }).catch(() => null);
    const followups = cleanFollowups(reply?.suggestions);
    const last = getChats(scope).find((c) => c.id === chatId)?.turns.at(-1);
    // Nothing is written otherwise, so a late reply does not store a deleted file's or set's chats again.
    if (!followups || last?.id !== turnId || last.result !== result) return;
    // Not through update(): no "could not be saved" notice for suggestions. The store moves the chat's time on, so
    // the server's copy gets them too.
    updateChats(scope, (list) => list.map((c) => (c.id === chatId ? { ...c, turns: [...c.turns.slice(0, -1), { ...last, followups }] } : c)));
    // Read out only where the chips show: the conversation on screen, no answer being written.
    if (chatId === latest.current.activeId && !sendingRef.current) announce(`Suggested questions: ${followups.join("; ")}`);
  }

  async function run(chatId: string, turnId: number, options: RunOptions) {
    sendingRef.current = true;
    setSendingId(chatId);
    setNotice(null);
    // Stop works from the start: it cancels uploads still in progress as well as the answer.
    const controller = new AbortController();
    abortRef.current = controller;
    const buffer: StreamBuffer = { turnId, text: "", frame: 0 };
    const takeBuffer = () => {
      if (buffer.frame) cancelAnimationFrame(buffer.frame);
      buffer.frame = 0;
      const text = buffer.text;
      buffer.text = "";
      return text;
    };
    let finished = false;
    let prompt = options.prompt ?? "";
    let datasetIds = getChats(scope).find((c) => c.id === chatId)?.datasetIds ?? [];
    try {
      if (attachments && (options.upload?.length || options.refresh)) {
        const files = options.upload ?? [];
        let added: number[] = [];
        if (files.length) {
          setLive(chatId, turnId, { steps: [files.length > 1 ? `Uploading ${files.length} files…` : `Uploading ${files[0].name}…`], text: "" });
          const settled = await Promise.allSettled(
            files.map((file) => uploadFile(file, (p) => !finished && setUploading((u) => ({ ...u, [file.name]: `${Math.round(p * 100)}%` })), controller.signal)),
          );
          const done: { file: File; detail: DatasetDetail }[] = [];
          const failed: File[] = [];
          let failure: Error | null = null;
          settled.forEach((outcome, i) => {
            if (outcome.status === "fulfilled") {
              done.push({ file: files[i], detail: outcome.value });
              attachments.onUploaded(outcome.value);
            } else {
              failed.push(files[i]);
              failure ??= outcome.reason as Error;
            }
          });
          setUploading({});
          // Files that did upload belong to the conversation even when a sibling failed.
          if (done.length) {
            added = done.map((d) => d.detail.id);
            datasetIds = [...new Set([...datasetIds, ...added])];
            const ids = datasetIds;
            updateChat(chatId, (c) => ({
              ...c,
              datasetIds: ids,
              turns: c.turns.map((t) => (t.id === turnId ? { ...t, files: linkCards(t.files, done) } : t)),
            }));
          }
          if (failed.length) {
            retryFiles.current.set(turnId, failed);
            if (controller.signal.aborted) throw new DOMException("Upload stopped", "AbortError");
            throw new Error(`${failed.map((f) => f.name).join(", ")} could not be uploaded. ${(failure as Error | null)?.message ?? ""}`.trim());
          }
        }
        setLive(chatId, turnId, { steps: ["Reading the files…"], text: "" });
        const documents = datasetIds.length ? await api.documents(datasetIds) : [];
        const ids = datasetIds;
        updateChat(chatId, (c) => ({
          ...c,
          datasetIds: ids,
          documents,
          turns: c.turns.map((t) => (t.id === turnId ? { ...t, files: labelCards(t.files, documents) } : t)),
        }));
        if (options.share) {
          // A sales register and a purchase register (now, or with files shared earlier): analyse them together.
          const fresh = added.length ? documents.filter((d) => added.includes(d.dataset_id)) : documents;
          const both = documents.some((d) => d.kind === "sales") && documents.some((d) => d.kind === "purchases");
          const brings = fresh.some((d) => d.kind === "sales" || d.kind === "purchases");
          if (!(both && brings && !blocked())) {
            updateTurn(chatId, turnId, (t) => ({ ...t, shared: true, live: undefined }));
            announce("Uploaded. Ask a question about it.");
            if (both && brings) setNotice(blocked());
            return;
          }
          prompt = COMPARE_PROMPT;
          updateTurn(chatId, turnId, (t) => ({ ...t, prompt }));
        }
      }

      const problem = blocked();
      if (problem || !selected) throw new Error(problem ?? "The server has no AI model set up.");
      setLive(chatId, turnId, { steps: [], text: "" });
      const steps: string[] = [];
      const flush = () => {
        const text = takeBuffer();
        if (text) updateTurn(chatId, turnId, (t) => ({ ...t, live: { ...(t.live ?? { steps: [], text: "" }), text: (t.live?.text ?? "") + text } }));
      };
      const onEvent = (event: ChatEvent) => {
        if (event.type === "delta") {
          buffer.text += event.text;
          if (!buffer.frame) buffer.frame = requestAnimationFrame(flush);
          return;
        }
        if (event.type === "reset") takeBuffer();
        else flush();
        if (event.type === "step") steps.push(event.text);
        updateTurn(chatId, turnId, (t) => {
          const live = t.live ?? { steps: [], text: "" };
          if (event.type === "step") return { ...t, live: { ...live, steps: [...live.steps, event.text].slice(-3) } };
          if (event.type === "reset") return { ...t, live: { ...live, text: "", note: event.text } };
          if (event.type === "analysis") return { ...t, live: { ...live, analysis: event.result } };
          return t;
        });
      };
      const result = await stream([...historyOf(options.before), { role: "user", content: prompt }], selected.id, onEvent, {
        fresh: options.fresh,
        signal: controller.signal,
        datasetIds,
      });
      takeBuffer();
      updateTurn(chatId, turnId, (t) => ({ ...t, result, steps: keptSteps(steps), live: undefined }));
      announce(readyText(result));
      void suggest(chatId, turnId, result, selected.id);
    } catch (error) {
      const rest = takeBuffer();
      if ((error as Error).name === "AbortError") {
        updateTurn(chatId, turnId, (t) => ({ ...t, stopped: true, partial: (t.live?.text ?? "") + rest, live: undefined }));
        announce("Stopped.");
      } else {
        let message = (error as Error).message;
        // A shared file was deleted from the library: drop it from the conversation instead of failing on every question.
        if (attachments && error instanceof ApiError && error.status === 404 && datasetIds.length) {
          const gone = await missingUploads(datasetIds);
          if (gone.length) {
            const chat = getChats(scope).find((c) => c.id === chatId);
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
        updateTurn(chatId, turnId, (t) => ({ ...t, error: message, live: undefined }));
        announce(message);
      }
    } finally {
      finished = true;
      if (abortRef.current === controller) abortRef.current = null;
      sendingRef.current = false;
      setUploading({});
      setSendingId(null);
    }
  }

  /** Ask a question in the conversation on screen (a new one when there is none). `prompt` replaces what is sent. */
  function ask(text: string, prompt?: string): boolean {
    const question = text.trim();
    if (!question) return false;
    if (sendingRef.current) {
      setNotice(BUSY);
      return false;
    }
    const problem = blocked();
    if (problem) {
      setNotice(problem);
      return false;
    }
    const chatId = active?.id ?? startChat(question);
    const before = active?.turns ?? [];
    const id = Date.now();
    addTurn(chatId, { id, question, prompt: prompt && prompt !== question ? prompt : undefined, live: { steps: [], text: "" } });
    void run(chatId, id, { prompt: prompt ?? question, before });
    return true;
  }

  /** Share Excel / CSV files: they upload into the conversation on screen (a new one when there is none). */
  function share(list: FileList | File[]) {
    if (!attachments) return;
    const all = [...list];
    const files = all.filter(isAccepted).slice(0, MAX_FILES);
    if (files.length < all.length) {
      setNotice(
        files.length < all.filter(isAccepted).length
          ? `Up to ${MAX_FILES} files at a time.`
          : `Only Excel and CSV files can be shared (${ACCEPTED.join(", ")}).`,
      );
    }
    if (!files.length) return;
    if (sendingRef.current) return setNotice(BUSY);
    if (!health) return setNotice(CONNECTING);
    void api.warmAi(); // a question about them is coming: open the connection now
    const chatId = active?.id ?? startChat(files.map((f) => f.name).join(", "));
    const id = Date.now();
    const cards: SharedFile[] = files.map((f) => ({ name: f.name, size: f.size }));
    addTurn(chatId, { id, question: "", files: cards, live: { steps: [], text: "" } });
    void run(chatId, id, { upload: files, share: true, before: active?.turns ?? [] });
  }

  function stop() {
    abortRef.current?.abort();
  }

  /** Answer the last turn again (or upload its files again when that is what failed). */
  function regenerate() {
    const last = turns.at(-1);
    if (!last || !active || sendingRef.current) return;
    const retry = retryFiles.current.get(last.id) ?? [];
    retryFiles.current.delete(last.id);
    const shareOnly = !last.question && !last.prompt;
    if (!shareOnly) {
      const problem = blocked();
      if (problem) return setNotice(problem);
    }
    updateTurn(active.id, last.id, (t) => ({
      ...t,
      result: undefined,
      error: undefined,
      stopped: undefined,
      partial: undefined,
      shared: undefined,
      followups: undefined,
      live: { steps: [], text: "" },
    }));
    void run(active.id, last.id, {
      prompt: last.prompt ?? last.question,
      upload: retry,
      // Shared files are read again (their upload or the documents step may be what failed).
      refresh: shareOnly || Boolean(last.error && last.files?.length),
      share: shareOnly,
      fresh: true,
      before: turns.slice(0, -1),
    });
  }

  async function compare() {
    if (!attachments?.onCompare || !active || comparing) return;
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

  const onCopy = useCallback((turnId: number, text: string) => {
    void copyText(text);
    setCopied(turnId);
    window.setTimeout(() => setCopied((current) => (current === turnId ? null : current)), 1500);
  }, []);
  const onRegenerate = useCallback(() => latest.current.regenerate(), []);
  /** A suggested question tapped: asked as if it was typed and sent. Its chips go away, so focus moves to the text box. */
  const onFollowup = useCallback(
    (question: string) => {
      if (latest.current.ask(question)) inputRef?.current?.focus({ preventScroll: true });
    },
    [inputRef],
  );
  const onCompare = useCallback(() => void latest.current.compare(), []);

  const kinds = new Set((active?.documents ?? []).map((d) => d.kind));
  return {
    chats,
    active,
    turns,
    ready,
    sending,
    /** The conversation whose answer is being written (may be another than the one on screen). */
    sendingId,
    uploading,
    notice,
    setNotice,
    announcement,
    copied,
    comparing,
    compareError: compareError && compareError.chatId === active?.id ? compareError.message : null,
    canCompare: Boolean(attachments?.onCompare && kinds.has("sales") && kinds.has("purchases")),
    ask,
    share,
    stop,
    regenerate,
    onCopy,
    onRegenerate,
    onFollowup,
    onCompare,
    forgetRetries: (chat: Conversation) => chat.turns.forEach((t) => retryFiles.current.delete(t.id)),
  };
}

export type ChatEngine = ReturnType<typeof useChatEngine>;
