import { useCallback, useEffect, useRef, useState } from "react";

// The Web Speech API is not in TypeScript's DOM types yet: just the parts used here.
type Alternative = { transcript: string };
type SpeechResultList = ArrayLike<ArrayLike<Alternative> & { isFinal: boolean }>;
type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: { results: SpeechResultList }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/**
 * Dictation into the ask box with the browser's speech recognition (Chrome, Edge, Safari). Where there is none
 * (Firefox, the Android WebView) `supported` is false and the mic button is hidden. Indian English understands the
 * Hinglish the owner types too.
 */
export function useSpeech(onText: (text: string) => void, onProblem: (message: string) => void) {
  const [supported, setSupported] = useState(() => recognitionCtor() !== null);
  const [listening, setListening] = useState(false);
  const rec = useRef<Recognition | null>(null);
  const handlers = useRef({ onText, onProblem });
  handlers.current = { onText, onProblem };

  useEffect(() => () => rec.current?.abort(), []);

  /** Start listening; what is heard is added after `base` (the text already in the box). */
  function start(base: string) {
    const Ctor = recognitionCtor();
    if (!Ctor) return setSupported(false);
    const r = new Ctor();
    r.lang = "en-IN";
    r.interimResults = true;
    r.continuous = false;
    const prefix = base.trim() ? `${base.trimEnd()} ` : "";
    r.onresult = (event) => {
      let heard = "";
      for (let i = 0; i < event.results.length; i++) heard += event.results[i][0]?.transcript ?? "";
      handlers.current.onText(prefix + heard.trimStart());
    };
    r.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        handlers.current.onProblem("Voice input needs microphone permission.");
      } else if (event.error === "network" || event.error === "language-not-supported") {
        setSupported(false);
        handlers.current.onProblem("Voice input is not available here. Type the question instead.");
      } else if (event.error !== "aborted" && event.error !== "no-speech") {
        handlers.current.onProblem("Voice input stopped. Try again.");
      }
    };
    r.onend = () => {
      if (rec.current === r) rec.current = null;
      setListening(false);
    };
    try {
      r.start();
      rec.current = r;
      setListening(true);
    } catch {
      setSupported(false);
    }
  }

  const stop = useCallback(() => rec.current?.stop(), []);

  return { supported, listening, start, stop, toggle: (base: string) => (listening ? stop() : start(base)) };
}
