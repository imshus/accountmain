import { useEffect, useMemo, useRef, useState } from "react";
import { useToday } from "../books";
import type { RegisterKind } from "../router";
import type { VoucherRow } from "../types";
import { AppShell, Button, Notice, Skeleton, StatCard } from "../ui";
import { useBillTotals } from "./books/billTotal";
import { registerTotals } from "./books/register/RegisterParts";
import { useRegisterBills } from "./books/register/useRegisterBills";
import { rupees, WeeklySpend, weekOf, type SpendDay } from "./books/reports/ReportParts";
import "./books/reports/reports.css";

/**
 * A register's bills that count, at their bill totals: what the Sales and Purchase screens add up. The server sends
 * 500 bills at a time, so the older pages are read too, one after another: the totals are of every bill, and Total
 * Income never sets the latest 500 sales against a longer run of purchases. `whole` once none is left on the server.
 */
function useCountedBills(kind: RegisterKind) {
  const list = useRegisterBills(kind);
  const { rows, hasOlder, olderBusy, olderError, loadOlder } = list;
  // One request per list: a page that changed nothing (the books changed meanwhile) waits for the new list.
  const asked = useRef<VoucherRow[] | null>(null);
  useEffect(() => {
    if (!hasOlder || olderBusy || olderError || asked.current === rows) return;
    asked.current = rows;
    void loadOlder();
  }, [rows, hasOlder, olderBusy, olderError, loadOlder]);
  const totalled = useBillTotals(rows);
  const bills = useMemo(() => totalled.filter((v) => !v.cancelled), [totalled]);
  return { list, bills, whole: list.loaded && !hasOlder };
}

type Figures = { spent: number; income: number; week: SpendDay[] };

/** Reports (the owner's picture): Total Spent (purchases), Total Income (sales − purchases) and the week's spend. */
export default function ReportsScreen() {
  const sales = useCountedBills("sales");
  const purchases = useCountedBills("purchases");
  const today = useToday();
  const whole = sales.whole && purchases.whole;
  const figures = useMemo<Figures | null>(() => {
    if (!whole) return null;
    const spent = registerTotals(purchases.bills).paise;
    // The owner's rule: income = sales − purchases.
    return { spent, income: registerTotals(sales.bills).paise - spent, week: weekOf(purchases.bills, today) };
  }, [whole, sales.bills, purchases.bills, today]);
  // While the pages are read again (the screen opened again, or the books changed), the last whole figures stay.
  const [last, setLast] = useState(figures);
  if (figures && figures !== last) setLast(figures);
  const shown = figures ?? last;

  const error = sales.list.error ?? purchases.list.error ?? sales.list.olderError ?? purchases.list.olderError;
  const retry = () => {
    for (const { list } of [sales, purchases]) {
      if (list.error) list.reload();
      else if (list.olderError) void list.loadOlder();
    }
  };

  return (
    <AppShell tab="reports">
      <div aria-busy={!figures && !error}>
        <h1 className="rep-title">Reports</h1>

        {error ? (
          <div className="rep-notice">
            <Notice
              tone="error"
              action={
                <Button size="sm" variant="soft" onClick={retry}>
                  Retry
                </Button>
              }
            >
              Could not load the bills: {error}
            </Notice>
          </div>
        ) : null}

        {shown ? (
          <>
            <div className="rep-totals">
              <StatCard label="Total Spent" value={rupees(shown.spent)} tone="brand" />
              <StatCard label="Total Income" value={rupees(shown.income)} tone={shown.income < 0 ? "rose" : "mint"} />
            </div>
            <WeeklySpend days={shown.week} />
          </>
        ) : !error ? (
          <div className="rep-skeleton" role="status" aria-label="Loading reports">
            <Skeleton height={96} radius={16} />
            <Skeleton height={96} radius={16} />
            <Skeleton height={250} radius={16} />
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
