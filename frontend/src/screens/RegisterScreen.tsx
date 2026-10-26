import { useCallback, useEffect, useMemo, useState } from "react";
import { useBooks } from "../books";
import { formatCount, formatDMY } from "../format";
import { navigate, type RegisterKind } from "../router";
import type { VoucherRow } from "../types";
import { Button, EmptyState, Notice, Page, Skeleton } from "../ui";
import { useBillTotals } from "./books/billTotal";
import { RegisterRow, RegisterStats, registerTotals } from "./books/register/RegisterParts";
import { useRegisterBills } from "./books/register/useRegisterBills";
import { VoucherSheet, type SheetState } from "./books/txn/VoucherSheet";
import { byDay, partyNamesOf, partyOf } from "./books/txn/vouchers";

export type RegisterScreenProps = { kind: RegisterKind };

const LOOK = {
  sales: { title: "Sales", what: "sales", entry: "sale", button: "Sales entry", icon: "trend" },
  purchases: { title: "Purchase", what: "purchases", entry: "purchase", button: "Purchase entry", icon: "cart" },
} as const;

const STEP = 60;

/** The Sales or Purchase register (the owner's pictures): amount and net weight, then the bills by day, newest first. */
export default function RegisterScreen({ kind }: RegisterScreenProps) {
  const look = LOOK[kind];
  const books = useBooks();
  const list = useRegisterBills(kind);
  const rows = useBillTotals(list.rows);
  const [shown, setShown] = useState(STEP);
  const [sheet, setSheet] = useState<SheetState>(null);
  const [done, setDone] = useState<string | null>(null);

  const parties = useMemo(() => partyNamesOf(books.ledgers), [books.ledgers]);
  const bills = useMemo(() => rows.filter((v) => !v.cancelled), [rows]);
  const totals = useMemo(() => registerTotals(bills), [bills]);
  // Days newest first; within a day, the bills in the order they were made (as on the owner's Sales picture).
  const days = useMemo(() => byDay(bills.slice(0, shown)).map((day) => ({ ...day, rows: [...day.rows].reverse() })), [bills, shown]);

  const openBill = useCallback((v: VoucherRow) => setSheet({ voucher: v, party: partyOf(v, parties), mode: "details" }), [parties]);
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

  const first = !list.loaded && !list.error;
  const failed = Boolean(list.error) && bills.length === 0;
  const more = bills.length > shown;
  const canLoadOlder = !more && list.hasOlder;

  return (
    <Page title={look.title}>
      <div className="reg-screen" aria-busy={list.loading}>
        <div aria-live="polite">{done ? <Notice tone="success">{done}</Notice> : null}</div>

        {list.error ? (
          <Notice
            tone="error"
            action={
              <Button size="sm" variant="soft" onClick={list.reload}>
                Retry
              </Button>
            }
          >
            Could not load the bills: {list.error}
          </Notice>
        ) : null}

        {first ? (
          <div className="reg-skeleton" role="status" aria-label="Loading bills">
            <div className="reg-stats">
              <Skeleton height={80} radius={16} />
              <Skeleton height={80} radius={16} />
            </div>
            <Skeleton width={80} height={12} />
            <Skeleton height={124} radius={16} />
          </div>
        ) : failed ? null : (
          <RegisterStats paise={totals.paise} mg={totals.mg} />
        )}

        {/* A register of more than 500 bills is loaded in pages: say so, so the totals are not read as the whole register's. */}
        {list.hasOlder && bills.length ? <p className="reg-hint">Totals of the bills loaded so far · load older bills below for the rest.</p> : null}

        {!first && !failed && bills.length === 0 ? (
          <EmptyState
            icon={look.icon}
            title={list.hasOlder ? `No ${look.what} in the latest bills` : `No ${look.what} yet`}
            action={
              <Button variant="soft" icon={look.icon} onClick={() => navigate({ name: "entry", kind: look.entry })}>
                {look.button}
              </Button>
            }
          >
            {list.hasOlder ? "Load older bills below, or add a bill now." : `Pehla bill ${look.button} se daalo — yahan apne aap dikhega.`}
          </EmptyState>
        ) : null}

        {days.map((day) => (
          <section key={day.date} className="reg-day">
            <h2 className="reg-day__date">{formatDMY(day.date)}</h2>
            <ul className="reg-day__card">
              {day.rows.map((v) => (
                <RegisterRow key={v.id} bill={v} party={partyOf(v, parties)} onOpen={openBill} />
              ))}
            </ul>
          </section>
        ))}

        {more || canLoadOlder || list.olderError ? (
          <div className="reg-more">
            {more ? (
              <Button variant="plain" onClick={() => setShown((n) => n + STEP)}>
                Show more ({formatCount(bills.length - shown)} left)
              </Button>
            ) : canLoadOlder ? (
              <Button variant="plain" icon="clock" busy={list.olderBusy} onClick={() => void list.loadOlder().then(() => setShown((n) => n + STEP))}>
                Load older bills
              </Button>
            ) : null}
            {list.olderError ? <Notice tone="error">Could not load older bills: {list.olderError}</Notice> : null}
          </div>
        ) : null}
      </div>

      <VoucherSheet
        state={sheet}
        onClose={() => setSheet(null)}
        onMode={(mode) => setSheet((cur) => (cur ? { ...cur, mode } : cur))}
        onCancel={cancel}
      />
    </Page>
  );
}
