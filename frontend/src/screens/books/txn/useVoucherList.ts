import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../../api";
import { useBooks } from "../../../books";
import { useSession } from "../../../session";
import type { VoucherRow } from "../../../types";

const PAGE = 200;

/**
 * Every entry the Transactions screen can show: the books' latest 200, plus older pages fetched on "Load older
 * entries". A search runs on the server when the books hold more entries than are loaded here.
 */
export function useVoucherList(query: string) {
  const { company, status } = useSession();
  const books = useBooks();
  const companyId = status === "ready" ? company?.id : undefined;
  // Older pages belong to one version of the books; any change starts again from the latest.
  const [older, setOlder] = useState<{ version: number; rows: VoucherRow[] }>({ version: -1, rows: [] });
  const [olderBusy, setOlderBusy] = useState(false);
  const [olderError, setOlderError] = useState<string | null>(null);
  const [found, setFound] = useState<{ query: string; version: number; rows: VoucherRow[]; total: number } | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const rows = useMemo(() => {
    const extra = older.version === books.version ? older.rows : [];
    if (!extra.length) return books.vouchers;
    const seen = new Set(books.vouchers.map((v) => v.id));
    return [...books.vouchers, ...extra.filter((v) => !seen.has(v.id))];
  }, [books.vouchers, books.version, older]);
  const hasOlder = books.voucherTotal > rows.length;

  const loadOlder = useCallback(async () => {
    if (!companyId) return;
    setOlderBusy(true);
    setOlderError(null);
    const version = books.version;
    try {
      const page = await api.vouchers(companyId, { offset: String(rows.length), limit: String(PAGE) });
      setOlder((cur) => ({ version, rows: [...(cur.version === version ? cur.rows : []), ...page.rows] }));
    } catch (e) {
      setOlderError(e instanceof Error ? e.message : String(e));
    } finally {
      setOlderBusy(false);
    }
  }, [companyId, books.version, rows.length]);

  // Not everything is loaded: ask the server, so a search finds old entries too.
  const q = query.trim();
  const serverSearch = q.length > 0 && hasOlder;
  useEffect(() => {
    if (!serverSearch || !companyId) return;
    let live = true;
    const version = books.version;
    const timer = window.setTimeout(() => {
      api.vouchers(companyId, { search: q, limit: String(PAGE) }).then(
        (page) => {
          if (!live) return;
          setFound({ query: q, version, rows: page.rows, total: page.total });
          setSearchError(null);
        },
        (e: unknown) => live && setSearchError(e instanceof Error ? e.message : String(e)),
      );
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [serverSearch, q, companyId, books.version]);

  const searchHits = serverSearch && found && found.query === q && found.version === books.version ? found : null;
  return {
    rows,
    hasOlder,
    loadOlder,
    olderBusy,
    olderError,
    /** Server results for the query (null: filter `rows` locally). */
    searchHits,
    searching: serverSearch && !searchHits && !searchError,
    searchError: serverSearch ? searchError : null,
  };
}
