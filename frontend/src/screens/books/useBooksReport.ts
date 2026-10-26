import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { useBooks } from "../../books";
import { useSession } from "../../session";
import type { Report } from "../../types";

/**
 * useCompanyReport with a small shared cache: the Stock, Reports and bell screens ask for the same reports, and
 * coming Back to a screen shows the last figures at once (so the scroll position can be restored) while they reload.
 * Entries are tied to the books' version, so any saved or cancelled entry makes them fetch again.
 */

type Entry = { version: number; report: Report | null; pending: Promise<Report> | null };
const cache = new Map<string, Entry>();
const MAX_ENTRIES = 24;

function fetchReport(key: string, companyId: number, kind: string, params: Record<string, string>, version: number, force: boolean) {
  const hit = cache.get(key);
  if (!force && hit && hit.version === version) {
    if (hit.pending) return hit.pending;
    if (hit.report) return Promise.resolve(hit.report);
  }
  const pending = api.companyReport(companyId, kind, params).then(
    (report) => {
      cache.delete(key); // re-insert: the Map keeps insertion order, oldest first
      cache.set(key, { version, report, pending: null });
      while (cache.size > MAX_ENTRIES) cache.delete(cache.keys().next().value as string);
      return report;
    },
    (error: unknown) => {
      const now = cache.get(key);
      if (now?.pending === pending) cache.set(key, { ...now, pending: null, version: -1 });
      throw error;
    },
  );
  cache.set(key, { version, report: hit?.report ?? null, pending });
  return pending;
}

type State = { key: string; report: Report | null; error: string | null; loading: boolean };

/** A company report ("dashboard", "stock_grams", ...). `enabled` false skips the request (e.g. a metal not in use). */
export function useBooksReport(kind: string, params: Record<string, string> = {}, enabled = true) {
  const { company, status } = useSession();
  const { version } = useBooks();
  const companyId = status === "ready" ? company?.id : undefined;
  const query = JSON.stringify(params);
  const key = companyId && enabled ? `${companyId}|${kind}|${query}` : "";
  const [state, setState] = useState<State>({ key: "", report: null, error: null, loading: false });
  const [nonce, setNonce] = useState(0);
  const seenNonce = useRef(0);

  useEffect(() => {
    if (!key || !companyId) return;
    let live = true;
    const force = seenNonce.current !== nonce;
    seenNonce.current = nonce;
    setState((s) => ({ key, report: s.key === key ? s.report : (cache.get(key)?.report ?? null), error: null, loading: true }));
    fetchReport(key, companyId, kind, JSON.parse(query) as Record<string, string>, version, force).then(
      (report) => live && setState({ key, report, error: null, loading: false }),
      (e: unknown) => live && setState((s) => ({ ...s, key, error: e instanceof Error ? e.message : String(e), loading: false })),
    );
    return () => {
      live = false;
    };
  }, [key, companyId, kind, query, version, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  // Until the effect runs for a new key, show what the cache has rather than another report's figures.
  const current: State = state.key === key ? state : { key, report: key ? (cache.get(key)?.report ?? null) : null, error: null, loading: !!key };
  return { report: current.report, loading: current.loading, error: current.error, reload };
}
