import type { Conversation, Turn } from "./chatStore";

/**
 * The AI conversations kept on the server too, so they survive a new phone or a reinstall. The lists on the device
 * (chatStore) stay the working copy: a changed conversation is sent a moment later (never while an answer is being
 * written), a delete at once, and each scope is read from the server once per connection and merged in, the newer
 * copy of a conversation winning. Requests that fail wait in a small queue on the device and are tried again. An
 * older server without these routes turns this off until the app restarts: the chats then stay on the device only
 * (deletes still wait in the queue, so the server's copies do not come back later).
 */

/** A conversation deleted on some device, with the time it carried (``updated``). */
export type Tombstone = { id: string; updated: number };

/**
 * What still has to reach the server: the latest per conversation (``scope`` + ``id``). "forget" deletes every
 * conversation of a deleted file or set changed at or before ``updated``, the ones other devices kept included.
 */
export type PendingOp = { kind: "put" | "delete" | "forget"; scope: string; id: string; updated: number };

export type ChatServer = {
  list: (scope: string) => Promise<{ chats?: unknown; deleted?: unknown } | null>;
  /** ``chat`` is the copy the server kept; null with ``deleted`` when a newer delete (from any device) won. */
  put: (scope: string, chat: Conversation) => Promise<{ chat?: unknown; deleted?: unknown } | null>;
  remove: (scope: string, id: string, updated: number) => Promise<unknown>;
  /** Whether the server answers its health check (after a request that got no usable answer). */
  up: () => Promise<boolean>;
};

export type SyncedStore = {
  get: (scope: string) => Conversation[];
  /** Put a merged list in place (kept on the device, screens told) without it counting as a change to send. */
  replace: (scope: string, chats: Conversation[]) => void;
  /** A conversation as kept on the device; throws on a malformed record. */
  shape: (chat: Conversation) => Conversation;
  /** Every scope with conversations on this device. */
  scopes: () => string[];
  /** The most conversations a scope keeps. */
  max: number;
};

const SCOPE = /^(home|ds-[0-9]+|book-[0-9]+)$/;
const CHAT_ID = /^[A-Za-z0-9_-]{1,64}$/;
/** Not under "accountsai.chats.", where every key is a scope's list. */
const PENDING_KEY = "accountsai.chatsync.pending";
const MAX_PENDING = 300;
/** Changes to one conversation within this time go up as one request. */
const SEND_AFTER_MS = 1500;
/** The server refuses a conversation over 2 MB of JSON. */
const MAX_BYTES = 2_000_000;
/** An upload that fails on its own (the server answering everything else) is dropped after this many tries. */
const MAX_TRIES = 3;

const list = <T,>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : []);
const isLive = (chat: Conversation) => chat.turns.some((t) => t.live);
const keyOf = (op: { scope: string; id: string }) => `${op.scope}/${op.id}`;
const isTombstone = (value: unknown): value is Tombstone =>
  typeof (value as Tombstone | null)?.id === "string" && typeof (value as Tombstone).updated === "number";

/** The server's copy is the one to keep: newer, or as new but different (the server keeps its own on equal times). */
const serverWins = (mine: Conversation, theirs: Conversation, shape: (chat: Conversation) => Conversation) =>
  theirs.updated > mine.updated || (theirs.updated === mine.updated && JSON.stringify(shape(mine)) !== JSON.stringify(theirs));

/** A turn as JSON without its query and analysis rows, which a copy cut down on a device lacks. */
const withoutRows = (turn: Turn) =>
  JSON.stringify({
    ...turn,
    result: turn.result && {
      ...turn.result,
      queries: turn.result.queries.map((q) => ({ ...q, rows: [] })),
      analyses: turn.result.analyses?.map((a) => ({ ...a, rows: [] })),
    },
  });

/**
 * ``mine``, read back cut down (``trimmed``) and changed here since, completed from the server's older copy: the
 * turns before its first, and the rows of every turn it has unchanged. Without one, it is all there is.
 */
function complete(mine: Conversation, whole?: Conversation): Conversation {
  const { trimmed: _trimmed, ...chat } = mine;
  if (!whole) return chat;
  const theirs = new Map(whole.turns.map((t) => [t.id, t]));
  const first = whole.turns.findIndex((t) => t.id === mine.turns[0]?.id);
  const turns = mine.turns.map((t) => {
    const full = theirs.get(t.id);
    return full && withoutRows(full) === withoutRows(t) ? full : t;
  });
  return { ...chat, turns: [...whole.turns.slice(0, Math.max(first, 0)), ...turns] };
}

export type Merged = {
  chats: Conversation[];
  /** The device's conversations that the server lacks or has an older copy of. */
  upload: Conversation[];
  /** Removed here because they were deleted on some device. */
  removed: string[];
  changed: boolean;
};

/**
 * One scope's conversations merged with the server's. The newer copy of each wins; on equal times the server's when
 * they differ (``shape``: a conversation as sent), as on the server. One deleted on any device at or after its last
 * change goes (``deleted``: the server's tombstones and the deletes not sent yet; ``cutoff``: when the scope's file
 * or set was deleted here); the server's other conversations fill the list up to ``max``, newest first (the device's
 * own are never dropped here). A conversation whose answer is still being written is never replaced or removed. A
 * copy read back cut down that is still the newer is completed from the server's before it is sent.
 */
export function mergeChats(
  local: Conversation[],
  remote: Conversation[],
  deleted: Tombstone[],
  cutoff = 0,
  max = Infinity,
  shape = (chat: Conversation) => chat,
): Merged {
  const tombs = new Map<string, number>();
  for (const t of deleted) tombs.set(t.id, Math.max(tombs.get(t.id) ?? -Infinity, t.updated));
  const gone = (chat: Conversation) => chat.updated <= cutoff || (tombs.get(chat.id) ?? -Infinity) >= chat.updated;
  const theirs = new Map<string, Conversation>();
  for (const chat of remote) if ((theirs.get(chat.id)?.updated ?? -Infinity) < chat.updated) theirs.set(chat.id, chat);

  const chats: Conversation[] = [];
  const upload: Conversation[] = [];
  const removed: string[] = [];
  let changed = false;
  for (const mine of local) {
    const other = theirs.get(mine.id);
    theirs.delete(mine.id);
    if (isLive(mine)) {
      chats.push(mine);
    } else if (other && !gone(other) && serverWins(mine, other, shape)) {
      chats.push(other);
      changed = true;
    } else if (gone(mine)) {
      removed.push(mine.id);
      changed = true;
    } else {
      const kept = mine.trimmed ? complete(mine, other) : mine;
      if (kept !== mine) changed = true;
      chats.push(kept);
      if (!other || mine.updated > other.updated) upload.push(kept);
    }
  }
  const added = new Set([...theirs.values()].filter((c) => !gone(c)));
  if (!added.size) return { chats, upload, removed, changed };
  const all = [...chats, ...added].sort((a, b) => b.updated - a.updated).filter((c, i) => i < max || !added.has(c));
  return { chats: all, upload, removed, changed: changed || all.length > chats.length };
}

/**
 * ``op`` added to the queue: it replaces the conversation's earlier one (the latest wins), and "forget" replaces
 * everything waiting for its scope. Past ``max`` the oldest uploads go first (the next read of their scope finds
 * them again); deletes are kept.
 */
export function queueOp(pending: PendingOp[], op: PendingOp, max = MAX_PENDING): PendingOp[] {
  const next = pending.filter((p) => p.scope !== op.scope || (op.kind !== "forget" && p.id !== op.id));
  next.push(op);
  while (next.length > max) {
    const oldest = next.findIndex((p) => p.kind === "put");
    next.splice(Math.max(oldest, 0), 1);
  }
  return next;
}

function readPending(): PendingOp[] {
  try {
    return list<PendingOp>(JSON.parse(localStorage.getItem(PENDING_KEY) ?? "[]")).filter(
      (op) => ["put", "delete", "forget"].includes(op?.kind) && SCOPE.test(op.scope) && typeof op.id === "string" && typeof op.updated === "number",
    );
  } catch {
    return [];
  }
}

/** The sync for ``store``'s conversations through ``server``. chatStore makes the one the app uses. */
export function createChatSync(server: ChatServer, store: SyncedStore) {
  let ready = false;
  let epoch = 0;
  /** The server has no chat routes (an older backend): nothing more is sent until the app restarts. */
  let off = false;
  /** A request failed (offline, server down): the next one that works sends what is waiting. */
  let stalled = false;
  let pending = readPending();
  /** The connection (session epoch) each scope was last read in. */
  const pulled = new Map<string, number>();
  /** Conversations changed within the last moment: sent when their timer fires. */
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  const tooLarge = new Set<string>();
  /** Failed tries per op (``scope/id``) while the server answered other requests. */
  const failures = new Map<string, number>();
  let queue = Promise.resolve();
  let flushQueued = false;

  const active = () => ready && !off;

  /** One request at a time, in order, so a read never overtakes a delete sent before it. */
  function run(task: () => Promise<void>) {
    queue = queue.then(task).catch((error) => console.warn("Chat sync failed", error));
  }

  function save() {
    try {
      localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
    } catch {
      // Storage full or blocked: the queue is still kept in memory.
    }
  }

  function add(op: PendingOp) {
    if (SCOPE.test(op.scope) && (op.kind === "forget" || CHAT_ID.test(op.id))) pending = queueOp(pending, op);
  }

  function stopTimer(key: string) {
    clearTimeout(timers.get(key));
    timers.delete(key);
  }

  /** True when the request can never succeed (dropped); otherwise it is kept for the next try. */
  function hopeless(error: unknown): boolean {
    const status = (error as { status?: number } | null)?.status ?? 0;
    if (status === 404) {
      off = true;
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
      return false;
    }
    return status === 400 || status === 413 || status === 422;
  }

  /**
   * A request that may still work failed. False when the server is out of reach (or off): everything waits. True
   * when it still answers, so this request failed on its own (e.g. a web server refusing a large body without CORS
   * headers, or a slow upload running out of time): it goes to the back of the queue, and an upload is dropped
   * after a few tries (the next read of its scope finds the server's copy older and queues it again).
   */
  async function failedAlone(op: PendingOp): Promise<boolean> {
    if (off || !(await server.up())) return false;
    const key = keyOf(op);
    const tries = (failures.get(key) ?? 0) + 1;
    failures.set(key, tries);
    pending = pending.filter((p) => p !== op);
    if (op.kind !== "put" || tries < MAX_TRIES) pending.push(op);
    else console.warn(`The chat ${key} could not be sent (${tries} tries); it is tried again on the next connection.`);
    save();
    return true;
  }

  function worked() {
    if (!stalled) return;
    stalled = false;
    kick();
  }

  function clean(raw: unknown): Conversation | null {
    try {
      const chat = store.shape(raw as Conversation);
      return CHAT_ID.test(chat.id) && chat.turns.length ? chat : null;
    } catch {
      return null;
    }
  }

  /** What is sent for ``chat``, or null when there is nothing to send (no settled turn yet, or over 2 MB). */
  function bodyOf(chat: Conversation): Conversation | null {
    const body = clean(chat);
    if (!body) return null;
    if (new TextEncoder().encode(JSON.stringify(body)).length <= MAX_BYTES) return body;
    if (!tooLarge.has(chat.id)) {
      tooLarge.add(chat.id);
      console.warn(`The chat "${chat.title}" is over 2 MB, so it is kept on this device only.`);
    }
    return null;
  }

  /** The server kept another copy than the one sent (changed on another device meanwhile): show that one. */
  function adopt(scope: string, raw: unknown) {
    const kept = clean(raw);
    const chats = store.get(scope);
    const mine = kept && chats.find((c) => c.id === kept.id);
    if (kept && mine && !isLive(mine) && serverWins(mine, kept, store.shape)) store.replace(scope, chats.map((c) => (c === mine ? kept : c)));
  }

  /** The server kept a delete at least as new as the copy sent (deleted on another device): remove it here too. */
  function drop(scope: string, gone: Tombstone) {
    const chats = store.get(scope);
    const mine = chats.find((c) => c.id === gone.id);
    if (mine && !isLive(mine) && mine.updated <= gone.updated) store.replace(scope, chats.filter((c) => c !== mine));
  }

  /** Send one op; false when it has to wait (its conversation has an answer being written). */
  async function send(op: PendingOp): Promise<boolean> {
    if (op.kind === "delete") {
      await server.remove(op.scope, op.id, op.updated);
    } else if (op.kind === "forget") {
      const reply = await server.list(op.scope);
      for (const chat of list<unknown>(reply?.chats)) {
        if (isTombstone(chat) && chat.updated <= op.updated) await server.remove(op.scope, chat.id, chat.updated);
      }
    } else {
      const chat = store.get(op.scope).find((c) => c.id === op.id);
      if (chat && isLive(chat)) return false;
      if (chat?.trimmed) {
        // It would overwrite the server's whole copy: a read of the scope completes it first (merge).
        pull(op.scope);
        return false;
      }
      const body = chat && bodyOf(chat);
      if (!body) return true;
      const reply = await server.put(op.scope, body);
      if (reply?.chat === null && isTombstone(reply.deleted)) drop(op.scope, reply.deleted);
      else adopt(op.scope, reply?.chat);
    }
    worked();
    return true;
  }

  /**
   * Send what is waiting, oldest first but deletes before uploads (a later read cannot make up for a lost delete);
   * stops when the server is out of reach (kept for the next try).
   */
  function flush() {
    if (!active() || flushQueued) return;
    flushQueued = true;
    run(async () => {
      flushQueued = false;
      for (const op of [...pending].sort((a, b) => Number(a.kind === "put") - Number(b.kind === "put"))) {
        if (!active()) return;
        if (!pending.includes(op) || (op.kind === "put" && timers.has(keyOf(op)))) continue;
        try {
          if (!(await send(op))) continue;
        } catch (error) {
          if (!hopeless(error)) {
            if (await failedAlone(op)) continue;
            stalled = true;
            return;
          }
          console.warn(`The server refused the chat ${keyOf(op)}`, error);
        }
        failures.delete(keyOf(op));
        pending = pending.filter((p) => p !== op);
        save();
      }
    });
  }

  function merge(scope: string, reply: { chats?: unknown; deleted?: unknown }) {
    const waiting = pending.filter((op) => op.scope === scope);
    const deleted = [...list<unknown>(reply.deleted).filter(isTombstone), ...waiting.filter((op) => op.kind === "delete")];
    const cutoff = waiting.find((op) => op.kind === "forget")?.updated ?? 0;
    const remote = list<unknown>(reply.chats)
      .map(clean)
      .filter((c): c is Conversation => c !== null);
    const result = mergeChats(store.get(scope), remote, deleted, cutoff, store.max, store.shape);
    if (result.changed) store.replace(scope, result.chats);
    // One cut down whose answer was being written is completed by another read, once it is sent (send).
    if (result.chats.some((c) => c.trimmed)) pulled.delete(scope);
    for (const id of result.removed) {
      stopTimer(keyOf({ scope, id }));
      pending = pending.filter((op) => op.kind !== "put" || op.scope !== scope || op.id !== id);
    }
    for (const chat of result.upload) add({ kind: "put", scope, id: chat.id, updated: chat.updated });
    if (result.removed.length || result.upload.length) save();
  }

  /** Read a scope from the server and merge it in, once per connection. */
  function pull(scope: string) {
    if (!active() || !SCOPE.test(scope) || pulled.get(scope) === epoch) return;
    pulled.set(scope, epoch);
    run(async () => {
      if (!active()) {
        pulled.delete(scope);
        return;
      }
      let reply: { chats?: unknown; deleted?: unknown } | null;
      try {
        reply = await server.list(scope);
      } catch (error) {
        // Read again once the server is back. One that fails while it answers (e.g. too large to arrive in time)
        // waits for the next connection rather than being downloaded again after every request that works.
        if (hopeless(error) || off || (await server.up())) return;
        pulled.delete(scope);
        stalled = true;
        return;
      }
      // Not this API (a server answering something else): behave like an older one.
      if (!reply || !Array.isArray(reply.chats)) {
        off = true;
        return;
      }
      worked();
      merge(scope, reply);
      flush();
    });
  }

  /** Waiting changes first, then every scope not read in this connection yet. */
  function kick() {
    flush();
    for (const scope of store.scopes()) pull(scope);
  }

  if (typeof window !== "undefined") window.addEventListener("online", kick);

  return {
    /** A scope's conversations were read from the device for the first time. */
    opened: pull,
    /** A scope's list changed on this device: send the changed conversations (in a moment) and the removed ones. */
    changed(scope: string, before: Conversation[], next: Conversation[]) {
      if (!SCOPE.test(scope)) return;
      const was = new Map(before.map((c) => [c.id, c]));
      const kept = new Set(next.map((c) => c.id));
      let deleted = false;
      let queued = false;
      for (const chat of before) {
        if (kept.has(chat.id)) continue;
        stopTimer(keyOf({ scope, id: chat.id }));
        add({ kind: "delete", scope, id: chat.id, updated: chat.updated });
        deleted = queued = true;
      }
      for (const chat of next) {
        // A conversation with an answer being written is sent once the answer is in (that is a change too). Off,
        // only deletes wait (sent once the server has these routes); the next read finds the changes anyway.
        if (off || was.get(chat.id) === chat || isLive(chat) || !chat.turns.length) continue;
        const key = keyOf({ scope, id: chat.id });
        add({ kind: "put", scope, id: chat.id, updated: chat.updated });
        queued = true;
        stopTimer(key);
        timers.set(
          key,
          setTimeout(() => {
            timers.delete(key);
            flush();
          }, SEND_AFTER_MS),
        );
      }
      if (queued) save();
      if (deleted) flush();
    },
    /** A file or set was deleted: delete its conversations on the server too, other devices' included. */
    forgot(scope: string) {
      if (!SCOPE.test(scope)) return;
      for (const key of [...timers.keys()]) if (key.startsWith(`${scope}/`)) stopTimer(key);
      add({ kind: "forget", scope, id: "*", updated: Date.now() });
      save();
      flush();
    },
    /** The session's state: requests go only while it is ready, and every scope is read again per connection. */
    session(isReady: boolean, at: number) {
      ready = isReady;
      epoch = at;
      if (isReady) kick();
    },
  };
}
