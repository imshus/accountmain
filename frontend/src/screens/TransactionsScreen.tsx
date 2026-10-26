import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useBooks, useToday } from "../books";
import { formatCount } from "../format";
import { cameBack, navigate } from "../router";
import { useCompany } from "../session";
import type { VoucherRow } from "../types";
import { AppShell, Button, EmptyState, Notice, Skeleton, Spinner } from "../ui";
import { BellScope } from "./books/BellScope";
import { useBillTotals } from "./books/billTotal";
import { TxnCard } from "./books/txn/TxnCard";
import { TxnSearch } from "./books/txn/TxnSearch";
import { useVoucherList } from "./books/txn/useVoucherList";
import { VoucherSheet, type SheetState } from "./books/txn/VoucherSheet";
import { matches, nameOf, partyNamesOf, partyOf, whenOf } from "./books/txn/vouchers";
import "./books/txn/txn.css";

export type TransactionsScreenProps = {
  /** Opened from the header's search button: focus the search box. */
  search: boolean;
};

const STEP = 40;

// The search and the list's length are kept here while the app is open, so Back from an entry's books lands on the
// same list and scroll position.
let kept: { companyId: number; query: string; searchOpen: boolean; shown: number } | null = null;

/** Every entry, newest first, one card each (the owner's picture); search from the header, press and hold to cancel. */
export default function TransactionsScreen({ search }: TransactionsScreenProps) {
  const company = useCompany();
  const books = useBooks();
  const [memo] = useState(() => (kept?.companyId === company.id && cameBack() ? kept : null));
  const [query, setQuery] = useState(memo?.query ?? "");
  const [searchOpen, setSearchOpen] = useState(search || !!memo?.searchOpen);
  const [shown, setShown] = useState(memo?.shown ?? STEP);
  const [sheet, setSheet] = useState<SheetState>(null);
  const [done, setDone] = useState<string | null>(null);
  const searchBox = useRef<HTMLInputElement>(null);
  const list = useVoucherList(query);
  const rows = useBillTotals(list.searchHits?.rows ?? list.rows);

  useEffect(() => {
    kept = { companyId: company.id, query, searchOpen, shown };
  }, [company.id, query, searchOpen, shown]);

  // Opened by the header's search button: put the cursor in the box.
  useEffect(() => {
    if (search) searchBox.current?.focus();
  }, [search]);

  // Entries made elsewhere (the web, a second phone) show up when the screen opens and when the app comes back to the
  // front. Back from an entry keeps the list, and its scroll position, as they were.
  const refreshBooks = books.refresh;
  useEffect(() => {
    if (!cameBack()) void refreshBooks();
    const onShow = () => {
      if (document.visibilityState === "visible") void refreshBooks();
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, [refreshBooks]);

  const openSearch = useCallback(() => {
    setSearchOpen(true);
    requestAnimationFrame(() => searchBox.current?.focus());
  }, []);
  const closeSearch = () => {
    setSearchOpen(false);
    setQuery("");
  };

  const parties = useMemo(() => partyNamesOf(books.ledgers), [books.ledgers]);
  const visible = useMemo(
    () => (list.searchHits ? rows : rows.filter((v) => matches(v, partyOf(v, parties), query))),
    [list.searchHits, rows, parties, query],
  );
  const today = useToday();

  const openDetails = useCallback((v: VoucherRow) => setSheet({ voucher: v, party: partyOf(v, parties), mode: "details" }), [parties]);
  const askCancel = useCallback((v: VoucherRow) => setSheet({ voucher: v, party: partyOf(v, parties), mode: "confirm" }), [parties]);
  const cancel = async (v: VoucherRow) => {
    await books.cancel(v.id);
    setSheet(null);
    setDone(`${v.vtype} ${v.number} cancelled. It stays in the audit trail.`);
  };
  useEffect(() => {
    if (!done) return;
    const timer = window.setTimeout(() => setDone(null), 5000);
    return () => window.clearTimeout(timer);
  }, [done]);

  const searched = query.trim();
  const first = books.loading && books.vouchers.length === 0 && !books.error;
  const empty = !books.loading && !books.error && books.voucherTotal === 0;
  // One button for both: the loaded entries not shown yet, then older pages from the server.
  const more = visible.length > shown;
  const canLoadOlder = list.hasOlder && !list.searchHits && !searched;
  // A search on the server sends its latest 200 matches: say how many there are in all.
  const hitsTotal = list.searchHits && list.searchHits.total > visible.length ? list.searchHits.total : null;
  const loadOlder = () => {
    if (more) setShown((n) => n + STEP);
    else void list.loadOlder().then(() => setShown((n) => n + STEP));
  };

  return (
    <BellScope onSearch={openSearch}>
      <AppShell tab="transactions" width="wide">
        <h1 className="txn-title">Transactions</h1>

        {searchOpen ? (
          <TxnSearch
            value={query}
            onChange={(next) => {
              setQuery(next);
              setShown(STEP);
            }}
            onClose={closeSearch}
            inputRef={searchBox}
            busy={list.searching}
          />
        ) : null}
        <p className={hitsTotal ? "txn-found" : "visually-hidden"} aria-live="polite">
          {!searched || list.searching
            ? ""
            : hitsTotal
              ? `Showing the latest ${formatCount(visible.length)} of ${formatCount(hitsTotal)} found`
              : `${formatCount(visible.length)} found`}
        </p>

        <div aria-live="polite">
          {done ? (
            <div className="txn-status">
              <Notice tone="success">{done}</Notice>
            </div>
          ) : null}
        </div>

        {books.error ? (
          <div className="txn-status">
            <Notice
              tone="error"
              action={
                <Button size="sm" variant="soft" onClick={() => void books.refresh()}>
                  Retry
                </Button>
              }
            >
              Could not load the entries: {books.error}
            </Notice>
          </div>
        ) : null}
        {list.searchError ? (
          <div className="txn-status">
            <Notice tone="error">Search failed: {list.searchError}</Notice>
          </div>
        ) : null}

        {first ? (
          <div className="txn-skeleton" role="status" aria-label="Loading entries">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={70} radius={16} />
            ))}
          </div>
        ) : null}

        {empty ? (
          <EmptyState
            icon="swap"
            title="No entries yet"
            action={
              <>
                <Button variant="soft" icon="trend" onClick={() => navigate({ name: "entry", kind: "sale" })}>
                  Sales entry
                </Button>
                <Button variant="plain" icon="cart" onClick={() => navigate({ name: "entry", kind: "purchase" })}>
                  Purchase entry
                </Button>
              </>
            }
          >
            Abhi koi entry nahi hai — Home se Sales ya Purchase daalo.
          </EmptyState>
        ) : null}

        {searched && !first && !empty && visible.length === 0 && !list.searching ? (
          <EmptyState icon="search" title={`Nothing matches “${searched}”`}>
            Try a party name or an invoice number.
          </EmptyState>
        ) : null}

        {list.searching && visible.length === 0 ? <Spinner>Searching all entries…</Spinner> : null}

        {visible.length ? (
          <ul className="txn-list">
            {visible.slice(0, shown).map((v) => (
              <TxnCard key={v.id} voucher={v} name={nameOf(v, parties)} when={whenOf(v.date, today)} onOpen={openDetails} onHold={askCancel} />
            ))}
          </ul>
        ) : null}

        {more || canLoadOlder || list.olderError ? (
          <div className="txn-more">
            {more || canLoadOlder ? (
              <Button variant="plain" icon="clock" busy={!more && list.olderBusy} onClick={loadOlder}>
                Load older entries
              </Button>
            ) : null}
            {list.olderError ? <Notice tone="error">Could not load older entries: {list.olderError}</Notice> : null}
          </div>
        ) : null}
      </AppShell>

      <VoucherSheet
        state={sheet}
        onClose={() => setSheet(null)}
        onMode={(mode) => setSheet((cur) => (cur ? { ...cur, mode } : cur))}
        onCancel={cancel}
      />
    </BellScope>
  );
}
