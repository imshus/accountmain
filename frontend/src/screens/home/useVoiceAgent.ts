import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { AskOutcome } from "./useChatEngine";

/**
 * The voice agent: a live conversation with GPT (OpenAI Realtime over WebRTC). The microphone goes to OpenAI and the
 * voice comes back on the same connection; the backend only starts the call (api.voiceCall), so no OpenAI key is on
 * the phone. Whatever is about the books or the shared files, the voice model hands to `ask` (the app's chat), and
 * then says the checked answer.
 */

export type VoiceStatus = "idle" | "connecting" | "listening" | "hearing" | "thinking" | "speaking" | "ended" | "error";
export type VoiceLine = { id: string; who: "you" | "ai"; text: string };
/** The app's answer to what the person asked by voice (or why it could not be done), for the voice to say. */
export type VoiceAsk = (request: string) => Promise<string>;

type Connection = { pc: RTCPeerConnection; dc: RTCDataChannel; mic: MediaStream; audio: HTMLAudioElement };
type OutputItem = { type?: string; name?: string; call_id?: string; arguments?: string };
type RealtimeEvent = {
  type: string;
  item_id?: string;
  delta?: string;
  transcript?: string;
  error?: { message?: string; code?: string };
  response?: { status?: string; output?: OutputItem[]; status_details?: { error?: { message?: string } } };
};

const MAX_LINES = 40;
/** A caption line waiting for the person's words (they arrive after the reply has started). */
const PENDING = "…";
/** A short drop (switching Wi-Fi to mobile data) may come back; only a longer one ends the call. */
const DROP_GRACE_MS = 8_000;
/** The call ends by itself after this long without anyone speaking, and after MAX_CALL_MS in all (cost). */
const QUIET_MS = 3 * 60_000;
const MAX_CALL_MS = 15 * 60_000;
/** The server refuses a new reply while one is being given; the spoken answer then waits for that one to end. */
const BUSY_REPLY = "conversation_already_has_active_response";

function micProblem(error: unknown): string {
  const name = (error as { name?: string })?.name;
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "The microphone is not allowed. Allow it for Accounts.ai (phone Settings → Apps → Accounts.ai → Permissions → Microphone) and tap the mic again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone was found on this device.";
  if (name === "NotReadableError") return "The microphone is busy in another app. Close it and tap the mic again.";
  return (error as Error)?.message || "The voice agent could not start.";
}

/** What the voice says back for a chat answer: the checked answer, plus the figures the check could not find. */
export function spokenAnswer(outcome: AskOutcome): string {
  const result = outcome.result;
  if (!result) return `The app could not do it: ${outcome.error ?? "no answer came back."}`;
  const check = result.verification;
  if (check?.status === "unverified" && check.unverified.length) {
    return `${result.answer}\n\n(These figures were not found in the data; tell the person to check them: ${check.unverified.join(", ")}.)`;
  }
  return result.answer;
}

export function useVoiceAgent(ask: VoiceAsk) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lines, setLines] = useState<VoiceLine[]>([]);
  const connection = useRef<Connection | null>(null);
  // The call being started: close() during "connecting" ends it too, and a start that was closed (or replaced by a
  // newer one) stops at its next step instead of going live with no screen open.
  const attempt = useRef(0);
  const starting = useRef<{ pc: RTCPeerConnection | null; mic: MediaStream | null } | null>(null);
  const askRef = useRef(ask);
  askRef.current = ask;
  // Requests being answered by the app: the voice waits for them, so silence then is "thinking", not "listening".
  const working = useRef(0);
  // One request at a time, in the order they were made (a second bill said while the first is being added).
  const queue = useRef<Promise<void>>(Promise.resolve());
  // A reply is being given; a spoken answer that is ready meanwhile asks for its reply when that one is done.
  const responding = useRef(false);
  const replyWaiting = useRef(false);
  const dropTimer = useRef<number | undefined>(undefined);
  const watchTimer = useRef<number | undefined>(undefined);
  const lastHeard = useRef(0);

  const put = useCallback((id: string, who: VoiceLine["who"], text: string, append = false) => {
    setLines((list) => {
      const at = list.findIndex((l) => l.id === id);
      if (at < 0) return [...list, { id, who, text }].slice(-MAX_LINES);
      const next = [...list];
      next[at] = { ...next[at], text: append && next[at].text !== PENDING ? next[at].text + text : text };
      return next;
    });
  }, []);

  const drop = useCallback((id: string) => setLines((list) => list.filter((l) => l.id !== id)), []);

  const close = useCallback(() => {
    attempt.current++;
    window.clearTimeout(dropTimer.current);
    window.clearInterval(watchTimer.current);
    const pending = starting.current;
    starting.current = null;
    pending?.mic?.getTracks().forEach((t) => t.stop());
    pending?.pc?.close();
    const c = connection.current;
    connection.current = null;
    working.current = 0;
    queue.current = Promise.resolve();
    responding.current = false;
    replyWaiting.current = false;
    if (!c) return;
    try {
      c.dc.close();
    } catch {
      // Already closed.
    }
    c.pc.close();
    c.mic.getTracks().forEach((t) => t.stop());
    c.audio.srcObject = null;
  }, []);

  const stop = useCallback(() => {
    close();
    setStatus("idle");
  }, [close]);

  const end = useCallback(
    (status: "ended" | "error", message: string) => {
      close();
      setError(message);
      setStatus(status);
    },
    [close],
  );

  useEffect(() => close, [close]); // leaving the screen ends the call

  const reply = useCallback((dc: RTCDataChannel) => {
    if (responding.current) {
      replyWaiting.current = true;
      return;
    }
    responding.current = true; // until response.done: two answers ready together ask for one reply
    dc.send(JSON.stringify({ type: "response.create" }));
  }, []);

  const answer = useCallback(
    (dc: RTCDataChannel, callId: string, args: string) => {
      const live = () => connection.current?.dc === dc && dc.readyState === "open";
      working.current++;
      setStatus("thinking");
      const run = async () => {
        let request = "";
        try {
          request = String((JSON.parse(args) as { request?: unknown }).request ?? "").trim();
        } catch {
          // Cut off: nothing is sent to the books.
        }
        let output: string;
        if (!request) {
          output = "The request did not come through. Ask the person to say it again.";
        } else {
          try {
            output = await askRef.current(request);
          } catch (e) {
            output = `The app could not do it: ${(e as Error).message}`;
          }
        }
        if (!live()) return; // the call ended meanwhile (and close() reset the count)
        working.current = Math.max(0, working.current - 1);
        lastHeard.current = Date.now();
        dc.send(JSON.stringify({ type: "conversation.item.create", item: { type: "function_call_output", call_id: callId, output } }));
        reply(dc);
        // A render between requests, so the next one is asked in the conversation this one started.
        await new Promise((r) => window.setTimeout(r, 50));
      };
      queue.current = queue.current.then(run, run);
    },
    [reply],
  );

  const handle = useCallback(
    (dc: RTCDataChannel, event: RealtimeEvent) => {
      switch (event.type) {
        case "input_audio_buffer.speech_started":
          lastHeard.current = Date.now();
          setStatus("hearing");
          // Their line goes in now, so it stays above the reply; the words fill in when transcribed.
          if (event.item_id) put(`you-${event.item_id}`, "you", PENDING);
          break;
        case "input_audio_buffer.speech_stopped":
          lastHeard.current = Date.now();
          setStatus("thinking");
          break;
        case "conversation.item.input_audio_transcription.completed":
          if (event.transcript?.trim()) put(`you-${event.item_id}`, "you", event.transcript.trim());
          else drop(`you-${event.item_id}`);
          break;
        case "conversation.item.input_audio_transcription.failed":
          drop(`you-${event.item_id}`);
          break;
        case "response.created":
          responding.current = true;
          break;
        case "response.output_audio_transcript.delta":
          if (event.delta) put(`ai-${event.item_id}`, "ai", event.delta, true);
          break;
        case "response.output_audio_transcript.done":
          if (event.transcript) put(`ai-${event.item_id}`, "ai", event.transcript);
          break;
        case "output_audio_buffer.started":
          lastHeard.current = Date.now();
          setStatus("speaking");
          break;
        case "output_audio_buffer.stopped": // the voice finished (response.done comes while it still plays)
          lastHeard.current = Date.now();
          setStatus(working.current ? "thinking" : "listening");
          break;
        case "response.done": {
          responding.current = false;
          const response = event.response;
          // Only a finished reply's tool call is run: one cut off by the person speaking again carries half a request
          // (the arguments event comes for those too), and the next reply asks again with all of it.
          if (response?.status === "completed") {
            for (const item of response.output ?? []) {
              if (item.type === "function_call" && item.name === "ask_books" && item.call_id) answer(dc, item.call_id, item.arguments ?? "{}");
            }
          } else if (response?.status === "failed") {
            setError(response.status_details?.error?.message || "The voice could not answer. Say it again.");
          }
          if (replyWaiting.current) {
            replyWaiting.current = false;
            reply(dc);
          }
          // A reply without voice (failed, cut off, or only a tool call already being answered) leaves nothing to wait for.
          setStatus((s) => (s === "thinking" && !working.current && !responding.current ? "listening" : s));
          break;
        }
        case "error":
          if (event.error?.code === BUSY_REPLY) replyWaiting.current = true; // asked again when the current reply ends
          else if (event.error?.message) setError(event.error.message);
          break;
      }
    },
    [answer, drop, put, reply],
  );

  const start = useCallback(async () => {
    if (connection.current || starting.current) return;
    const mine = ++attempt.current;
    const stale = () => attempt.current !== mine;
    const parts: { pc: RTCPeerConnection | null; mic: MediaStream | null } = { pc: null, mic: null };
    starting.current = parts;
    setError(null);
    setLines([]);
    setStatus("connecting");
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("This device cannot record from a microphone here.");
      const mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      parts.mic = mic;
      if (stale()) throw new DOMException("Closed", "AbortError");
      const pc = new RTCPeerConnection();
      parts.pc = pc;
      const audio = new Audio();
      audio.autoplay = true;
      pc.ontrack = (e) => {
        audio.srcObject = e.streams[0];
        void audio.play().catch(() => undefined);
      };
      for (const track of mic.getTracks()) pc.addTrack(track, mic);
      const dc = pc.createDataChannel("oai-events");
      dc.onopen = () => {
        if (connection.current?.dc === dc) setStatus("listening");
      };
      dc.onmessage = (e) => {
        if (connection.current?.dc !== dc) return; // a call that was closed: nothing it says is acted on
        try {
          handle(dc, JSON.parse(e.data as string) as RealtimeEvent);
        } catch {
          // Not an event this screen reads.
        }
      };
      pc.onconnectionstatechange = () => {
        if (connection.current?.pc !== pc) return;
        const state = pc.connectionState;
        if (state === "connected") window.clearTimeout(dropTimer.current);
        else if (state === "failed") end("error", "The voice connection dropped. Tap Try again to start again.");
        else if (state === "disconnected") {
          window.clearTimeout(dropTimer.current);
          dropTimer.current = window.setTimeout(() => {
            if (connection.current?.pc === pc && pc.connectionState !== "connected") {
              end("error", "The voice connection dropped. Tap Try again to start again.");
            }
          }, DROP_GRACE_MS);
        }
      };
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      if (stale()) throw new DOMException("Closed", "AbortError");
      const sdp = await api.voiceCall(offer.sdp ?? "");
      if (stale()) throw new DOMException("Closed", "AbortError");
      await pc.setRemoteDescription({ type: "answer", sdp });
      if (stale()) throw new DOMException("Closed", "AbortError");
      starting.current = null;
      connection.current = { pc, dc, mic, audio };
      if (dc.readyState === "open") setStatus("listening");
      const began = Date.now();
      lastHeard.current = began;
      watchTimer.current = window.setInterval(() => {
        if (connection.current?.pc !== pc || working.current) return;
        const now = Date.now();
        if (now - began > MAX_CALL_MS) end("ended", "The voice conversation ended after 15 minutes. Tap Start again to keep talking.");
        else if (now - lastHeard.current > QUIET_MS) end("ended", "The voice conversation ended after 3 quiet minutes. Tap Start again to keep talking.");
      }, 15_000);
    } catch (e) {
      parts.mic?.getTracks().forEach((t) => t.stop());
      parts.pc?.close();
      if (stale()) return; // closed or restarted meanwhile: that one owns the screen now
      starting.current = null;
      setError(e instanceof Error && (e as { status?: number }).status !== undefined ? e.message : micProblem(e));
      setStatus("error");
    }
  }, [end, handle]);

  return { status, error, lines, start, stop };
}
