import { useCallback, useEffect, useMemo, useRef, useState, type ClipboardEvent } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { useBooks } from "../books";
import { useLibrary } from "../library";
import { navigate } from "../router";
import { useSession } from "../session";
import { AppShell, Composer, Icon, Menu, MenuItem } from "../ui";
import { HOME_SCOPE } from "./home/chatStore";
import { ChatThread } from "./home/ChatThread";
import { ACCEPTED, isAccepted } from "./home/chatUtils";
import { HomeChatBar } from "./home/HomeChatBar";
import { HomeIntro } from "./home/HomeIntro";
import { useChatEngine, type Attachments, type ChatStream } from "./home/useChatEngine";
import { useFileDrop } from "./home/useFileDrop";
import { useFollow } from "./home/useFollow";
import { useSpeech } from "./home/useSpeech";
import "./home/Home.css";

export type HomeScreenProps = {
  /** Open this saved conversation (from History, route #/chat/<id>); none = the start screen. */
  chatId?: string;
  /** False while another screen is showing: Home stays mounted but hidden, so a streaming answer keeps arriving. */
  active: boolean;
};

// Extensions for browsers, MIME types for the Android file picker.
const PICKER_ACCEPT = [
  ...ACCEPTED,
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "application/vnd.ms-excel.sheet.macroEnabled.12",
  "text/csv",
].join(",");

/**
 * Home (the owner's picture): the "Add data" and "Report" pills; asking a question or sharing a file turns it into the
 * AI chat (chat.html). Each conversation has its own address (#/chat/<id>), so Back, or the Home tab, returns to the
 * start screen.
 */
export default function HomeScreen({ chatId, active }: HomeScreenProps) {
  const { health, company, status } = useSession();
  const { changed } = useBooks();
  const { putDataset } = useLibrary();
  const companyId = status === "ready" ? (company?.id ?? null) : null;

  // The company goes with every question, so the AI can add a shared sales or purchase sheet to its books; when it
  // did, the books are read again and the Sales / Purchase / Stock screens show the new bills at once. An answer that
  // was stopped or failed may have added the sheet before that, so the books are read again then too.
  const stream = useCallback<ChatStream>(
    async (messages, provider, onEvent, options) => {
      let imported = true;
      try {
        const result = await api.filesChatStream(options.datasetIds ?? [], companyId, messages, provider, onEvent, options);
        imported = Boolean(result.imports?.length);
        return result;
      } finally {
        if (companyId && imported) changed();
      }
    },
    [companyId, changed],
  );

  const [text, setText] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  // The chat itself compares a sales and a purchase register, so there is no separate report screen to open.
  const attachments = useMemo<Attachments>(() => ({ onUploaded: putDataset }), [putDataset]);

  const engine = useChatEngine({
    scope: HOME_SCOPE,
    health,
    stream,
    activeId: chatId ?? null,
    // A stale #/chat/<id> (deleted in History) is replaced, not stacked under the new chat.
    onStarted: (id) => navigate({ name: "home", chat: id }, { replace: Boolean(chatId) }),
    attachments,
    inputRef,
  });
  const { active: chat, turns, notice, setNotice } = engine;
  const inChat = turns.length > 0;

  const speech = useSpeech(setText, setNotice);
  const dragging = useFileDrop(active, (files) => engine.share(files));
  const follow = useFollow(active && inChat, threadRef, turns, chat?.id ?? null);

  // Hidden behind another screen: stop dictation and close the attach menu.
  const stopListening = speech.stop;
  useEffect(() => {
    if (active) return;
    stopListening();
    setMenuOpen(false);
  }, [active, stopListening]);

  const askRef = useRef(engine.ask);
  askRef.current = engine.ask;
  const onAsk = useCallback((question: string, prompt: string) => void askRef.current(question, prompt), []);

  function submit() {
    if (speech.listening) speech.stop();
    if (engine.ask(text)) setText("");
  }

  function pickFiles() {
    setMenuOpen(false);
    fileRef.current?.click();
  }

  function newChat() {
    setText("");
    setNotice(null);
    navigate({ name: "home" });
    window.setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 0);
  }

  function onPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const files = [...event.clipboardData.files].filter(isAccepted);
    if (!files.length) return;
    event.preventDefault();
    engine.share(files);
  }

  const elsewhere = engine.sendingId !== null && engine.sendingId !== chat?.id;
  const above = notice ? (
    <p className="home-notice" role="status">
      <span>{notice}</span>
      <button type="button" className="home-notice__close" onClick={() => setNotice(null)} aria-label="Dismiss">
        <Icon name="close" size={14} />
      </button>
    </p>
  ) : elsewhere ? (
    <p className="home-notice" role="status">
      <span>An answer is being written in another chat.</span>
      <button type="button" className="home-notice__link" onClick={() => navigate({ name: "home", chat: engine.sendingId! })}>
        Open it
      </button>
    </p>
  ) : null;

  const composer = (
    <div className="home-dock">
      {inChat && !follow.stuck ? (
        <button type="button" className="home-jump" onClick={follow.jump} aria-label="Jump to the latest">
          <Icon name="down" size={18} />
        </button>
      ) : null}
      <Composer
        value={text}
        onChange={setText}
        onSubmit={submit}
        busy={engine.sending}
        onStop={engine.stop}
        onMic={speech.supported ? () => speech.toggle(text) : undefined}
        listening={speech.listening}
        placeholder={speech.listening ? "Listening…" : undefined}
        menuOpen={menuOpen}
        onMenuToggle={setMenuOpen}
        menu={
          <Menu label="Attach">
            <MenuItem
              icon="camera"
              title="Click"
              badge="SOON"
              sub="Bill ki photo se entry"
              disabled
              onSelect={() => {
                setMenuOpen(false);
                setNotice("Bill ki photo abhi padhi nahi ja sakti — Excel / CSV file upload karo.");
              }}
            />
            <MenuItem icon="upload" title="Upload" sub="Excel / CSV file" highlight onSelect={pickFiles} />
          </Menu>
        }
        above={above}
        onPaste={onPaste}
        inputRef={inputRef}
      />
    </div>
  );

  return (
    <AppShell tab="home" composer={composer}>
      <input
        ref={fileRef}
        type="file"
        accept={PICKER_ACCEPT}
        multiple
        hidden
        onChange={(event) => {
          if (event.target.files?.length) engine.share(event.target.files);
          event.target.value = "";
        }}
      />
      {inChat && chat ? (
        <div ref={threadRef} className="home-chat">
          <HomeChatBar title={chat.title} onNew={newChat} />
          <ChatThread engine={engine} onAsk={onAsk} />
        </div>
      ) : (
        <HomeIntro onUpload={pickFiles} onChat={() => inputRef.current?.focus()} />
      )}
      <p className="visually-hidden" aria-live="polite">
        {active ? engine.announcement : ""}
      </p>
      {dragging
        ? createPortal(
            <div className="home-drop" aria-hidden="true">
              <span>
                <Icon name="upload" size={28} />
                Drop Excel or CSV files to share them
              </span>
            </div>,
            document.body,
          )
        : null}
    </AppShell>
  );
}
