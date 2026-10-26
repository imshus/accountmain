import { useMemo, useState } from "react";
import { navigate } from "../router";
import { Badge, Button, EmptyState, Icon, Input, Notice, Overline, Page, Sheet } from "../ui";
import { deleteChat, HOME_SCOPE, useChats, type Conversation } from "./home/chatStore";
import { dayLabel, timeLabel } from "./home/chatUtils";
import "./home/History.css";

/** Menu → History: the AI chats kept on this device, newest first, by day. Open one on Home, or delete it. */
export default function HistoryScreen() {
  const all = useChats(HOME_SCOPE);
  const [query, setQuery] = useState("");
  const [doomed, setDoomed] = useState<Conversation | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const chats = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all
      .filter((c) => c.turns.length)
      .filter((c) => !q || c.title.toLowerCase().includes(q) || c.turns.some((t) => t.question.toLowerCase().includes(q)))
      .sort((a, b) => b.updated - a.updated);
  }, [all, query]);

  const groups = useMemo(() => {
    const out: { day: string; chats: Conversation[] }[] = [];
    for (const chat of chats) {
      const day = dayLabel(chat.updated);
      const group = out.at(-1);
      if (group?.day === day) group.chats.push(chat);
      else out.push({ day, chats: [chat] });
    }
    return out;
  }, [chats]);

  const total = all.filter((c) => c.turns.length).length;

  function remove() {
    if (!doomed) return;
    setProblem(deleteChat(HOME_SCOPE, doomed.id) ? null : "The list could not be saved on this device (storage is full or blocked).");
    setDoomed(null);
  }

  return (
    <Page
      title="History"
      right={
        <Button variant="soft" size="sm" icon="edit" onClick={() => navigate({ name: "home" })}>
          New chat
        </Button>
      }
    >
      {problem ? <Notice tone="error">{problem}</Notice> : null}
      {total > 4 ? (
        <div className="hist-search">
          <Icon name="search" size={18} />
          <Input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search chats" aria-label="Search chats" />
        </div>
      ) : null}

      {!total ? (
        <EmptyState
          icon="clock"
          title="No chats yet"
          action={
            <Button variant="brand" onClick={() => navigate({ name: "home" })}>
              Ask a question
            </Button>
          }
        >
          Your AI chats are kept on this device and listed here.
        </EmptyState>
      ) : !chats.length ? (
        <p className="hist-none">No chat matches “{query.trim()}”.</p>
      ) : (
        groups.map((group) => (
          <section key={group.day} className="hist-group" aria-label={group.day}>
            <Overline as="h2">{group.day}</Overline>
            <ul className="hist-list">
              {group.chats.map((chat) => (
                <HistoryRow key={chat.id} chat={chat} onDelete={() => setDoomed(chat)} />
              ))}
            </ul>
          </section>
        ))
      )}

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
    </Page>
  );
}

function HistoryRow({ chat, onDelete }: { chat: Conversation; onDelete: () => void }) {
  const questions = chat.turns.filter((t) => t.question || t.result).length;
  const files = [...new Set(chat.turns.flatMap((t) => (t.files ?? []).map((f) => f.name)))];
  const live = chat.turns.some((t) => t.live);
  const meta = [
    timeLabel(chat.updated),
    questions ? `${questions} answer${questions === 1 ? "" : "s"}` : null,
    files.length ? (files.length === 1 ? files[0] : `${files.length} files`) : null,
  ].filter(Boolean);
  return (
    <li className="hist-row">
      <button type="button" className="hist-open" onClick={() => navigate({ name: "home", chat: chat.id })}>
        <span className="hist-icon">
          <Icon name={files.length ? "file" : "clock"} size={18} />
        </span>
        <span className="hist-text">
          <strong>{chat.title || "Conversation"}</strong>
          <small>{meta.join(" · ")}</small>
        </span>
      </button>
      {live ? (
        <Badge tone="brand">Answering</Badge>
      ) : (
        <button type="button" className="hist-delete" onClick={onDelete} aria-label={`Delete “${chat.title || "Conversation"}”`} title="Delete chat">
          <Icon name="trash" size={17} />
        </button>
      )}
    </li>
  );
}
