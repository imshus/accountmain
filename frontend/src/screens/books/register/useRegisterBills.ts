import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../../api";
import { useBooks } from "../../../books";
import type { RegisterKind } from "../../../router";
import { useSession } from "../../../session";
import type { VoucherRow, VoucherType } from "../../../types";

// The server's largest page.
const PAGE = 500;
// A register's bills and their returns: a credit note takes back a sale, a debit note a purchase.
const TYPES: Record<RegisterKind, VoucherType[]> = { sales: ["Sales", "Credit Note"], purchases: ["Purchase", "Debit Note"] };

/** Each type's bills loaded so far (newest first) and how many the books hold. */
type Pages = { key: string; lists: { rows: VoucherRow[]; total: number }[] };

// The last pages of each register, so coming Back shows the bills at once (and the scroll position can be restored).
const kept = new Map<string, Pages>();
const MAX_KEPT = 8;

/** The server's order: newest date first, then the later entry. */
const newer = (a: VoucherRow, b: VoucherRow) => a.date > b.date || (a.date === b.date && a.id > b.id);

/**
 * The Sales or Purchase register's own bills, asked of the server by type 500 at a time, not picked out of the books'
 * latest entries of every kind: a register of a few hundred bills is loaded, and totalled, whole. Read again whenever
 * the books change.
 */
export function useRegisterBills(kind: RegisterKind) {
  const { company, status } = useSession();
  const { version } = useBooks();
  const companyId = status === "ready" ? company?.id : undefined;
  const key = companyId ? `${companyId}|${kind}` : "";
  const [pages, setPages] = useState<Pages | null>(() => kept.get(key) ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const [olderBusy, setOlderBusy] = useState(false);
  const [olderError, setOlderError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    let live = true;
    setLoading(true);
    setError(null);
    Promise.all(TYPES[kind].map((vtype) => api.vouchers(companyId, { vtype, limit: String(PAGE) }))).then(
      (lists) => {
        if (!live) return;
        keep({ key, lists });
        setPages({ key, lists });
        setLoading(false);
      },
      (e: unknown) => {
        if (!live) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      },
    );
    return () => {
      live = false;
    };
  }, [companyId, kind, key, version, nonce]);

  const current = pages?.key === key ? pages : key ? (kept.get(key) ?? null) : null;

  const rows = useMemo(() => {
    if (!current) return [];
    const all = current.lists.flatMap((list) => list.rows).sort((a, b) => (newer(a, b) ? -1 : newer(b, a) ? 1 : 0));
    // A type with more on the server ends the list at its oldest loaded bill: the other type's older bills wait for
    // "Load older", so no day below is missing one kind of bill.
    const cut = current.lists
      .filter((list) => list.rows.length < list.total)
      .map((list) => list.rows[list.rows.length - 1])
      .reduce<VoucherRow | undefined>((c, v) => (v && (!c || newer(v, c)) ? v : c), undefined);
    return cut ? all.filter((v) => !newer(cut, v)) : all;
  }, [current]);
  const hasOlder = Boolean(current?.lists.some((list) => list.rows.length < list.total));

  const loadOlder = useCallback(async () => {
    if (!companyId || !current) return;
    const from = current;
    setOlderBusy(true);
    setOlderError(null);
    try {
      const more = await Promise.all(
        TYPES[kind].map((vtype, i) => {
          const loaded = from.lists[i].rows.length;
          return loaded < from.lists[i].total ? api.vouchers(companyId, { vtype, offset: String(loaded), limit: String(PAGE) }) : null;
        }),
      );
      // The books changed meanwhile: the list has started again from the latest.
      if (kept.get(from.key) !== from) return;
      const next: Pages = {
        key: from.key,
        lists: from.lists.map((list, i) => {
          const page = more[i];
          if (!page) return list;
          const seen = new Set(list.rows.map((v) => v.id));
          return { rows: [...list.rows, ...page.rows.filter((v) => !seen.has(v.id))], total: page.total };
        }),
      };
      keep(next);
      setPages(next);
    } catch (e) {
      setOlderError(e instanceof Error ? e.message : String(e));
    } finally {
      setOlderBusy(false);
    }
  }, [companyId, kind, current]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { rows, loaded: current !== null, loading, error, reload, hasOlder, loadOlder, olderBusy, olderError };
}

function keep(pages: Pages) {
  kept.delete(pages.key); // re-insert: the Map keeps insertion order, oldest first
  kept.set(pages.key, pages);
  while (kept.size > MAX_KEPT) kept.delete(kept.keys().next().value as string);
}
