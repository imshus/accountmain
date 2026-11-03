import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../../ui";
import { useOverlay } from "../../ui/useOverlay";
import { useVoiceAgent, type VoiceAsk, type VoiceStatus } from "./useVoiceAgent";
import "./VoiceAgent.css";

/** What can be said, shown until the person speaks: the app does all of it by voice, in any language. */
const EXAMPLES = [
  "Isko sales me add kar do",
  "Ramesh ko 5 gram 18 carat ring becha, labour 500",
  "Hukum Chand se 10 gram 22K chain kharida",
  "Aaj ki total sale kitni hui?",
  "Gold ka stock kitna hai?",
  "Garg Jewellers ke kitne bills hain?",
];

const STATUS_TEXT: Record<VoiceStatus, string> = {
  idle: "Starting…",
  connecting: "Connecting…",
  listening: "Listening… speak in any language",
  hearing: "Hearing you…",
  thinking: "Working on it…",
  speaking: "Speaking…",
  ended: "Call ended",
  error: "Could not start",
};

type Props = {
  open: boolean;
  onClose: () => void;
  /** The app's answer to a spoken request: the chat engine (ask and wait), so it shows in the conversation too. */
  ask: VoiceAsk;
};

/**
 * The voice agent the mic opens: a live conversation with GPT that can do whatever the chat can (add bills and files
 * to sales or purchases, read the books, stock and reports), with captions of both sides and examples to start with.
 */
export function VoiceAgent({ open, onClose, ask }: Props) {
  const voice = useVoiceAgent(ask);
  const { start, stop } = voice;
  const linesRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  // Escape and the Android back button end the call (back must not leave the app or change the chat behind it).
  useOverlay(open, onClose, panelRef);

  useEffect(() => {
    if (!open) return;
    void start();
    return stop;
  }, [open, start, stop]);

  useEffect(() => {
    linesRef.current?.scrollTo({ top: linesRef.current.scrollHeight, behavior: "smooth" });
  }, [voice.lines]);

  if (!open) return null;
  const over = voice.status === "error" || voice.status === "ended";
  return createPortal(
    <div className="voice" role="dialog" aria-modal="true" aria-label="Voice agent">
      <div className="voice__panel" ref={panelRef} tabIndex={-1}>
        <header className="voice__head">
          <span className="voice__title">
            <Icon name="mic" size={18} /> Voice
          </span>
          <button type="button" className="voice__close" onClick={onClose} aria-label="End the voice conversation">
            <Icon name="close" size={18} />
          </button>
        </header>

        <div className={`voice__orb voice__orb--${voice.status}`} aria-hidden="true">
          <span className="voice__ring" />
          <span className="voice__core">
            <Icon name="mic" size={30} />
          </span>
        </div>
        <p className="voice__status" role="status" aria-live="polite">
          {STATUS_TEXT[voice.status]}
        </p>
        {voice.error && voice.status === "ended" ? (
          <p className="voice__note" role="status">
            {voice.error}
          </p>
        ) : voice.error ? (
          <p className="voice__error" role="alert">
            {voice.error}
          </p>
        ) : null}

        <div className="voice__lines" ref={linesRef} aria-live="polite">
          {voice.lines.length ? (
            voice.lines.map((line) => (
              <p key={line.id} className={`voice__line voice__line--${line.who}`}>
                {line.text}
              </p>
            ))
          ) : (
            <div className="voice__examples">
              <p className="voice__hint">Try saying</p>
              <ul>
                {EXAMPLES.map((example) => (
                  <li key={example}>“{example}”</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="voice__foot">
          {over ? (
            <button type="button" className="voice__retry" onClick={() => void start()}>
              <Icon name="refresh" size={18} /> {voice.status === "ended" ? "Start again" : "Try again"}
            </button>
          ) : null}
          <button type="button" className="voice__end" onClick={onClose}>
            <Icon name="close" size={18} /> End
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
