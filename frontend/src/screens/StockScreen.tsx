import { useEffect, useMemo } from "react";
import { navigate, type StockMetal } from "../router";
import { useCompany } from "../session";
import type { Report } from "../types";
import { Button, CheckList, EmptyState, Notice, Page, Segmented, Skeleton } from "../ui";
import { cardValue } from "./books/figures";
import { ItemCard, StockTotal, stockItems } from "./books/stock/StockParts";
import { useBooksReport } from "./books/useBooksReport";
import { stockWarnings } from "./books/useBookWarnings";

export type StockScreenProps = { metal: StockMetal };

const METALS: StockMetal[] = ["gold", "silver"];
const LABEL: Record<StockMetal, string> = { gold: "Gold", silver: "Silver" };

const metalsOf = (report: Report) => METALS.filter((m) => report.options.metals?.includes(m));

// Switching metal opens the screen afresh (a new address): the metals last seen keep the switch in place meanwhile.
let seen: { companyId: number; metals: StockMetal[] } | null = null;

/** Metal stock in grams from the books (the owner's picture): the total fine stock, then each item's net weight. */
export default function StockScreen({ metal }: StockScreenProps) {
  const company = useCompany();
  const { report, loading, error, reload } = useBooksReport("stock_grams", { metal });
  const items = useMemo(() => stockItems(report), [report]);
  // The bell's stock warnings ("Gold 22K: −4.350 g fine …") open this screen, so they are listed here too.
  const warnings = useMemo(() => stockWarnings(metal, report), [metal, report]);
  // No entries at all, not only none by item (opening stock has no items; an older server lists only items that went out).
  const noStock = report !== null && ["Opening", "Came in", "Closing"].every((label) => Math.abs(cardValue(report, label)) < 0.0005);
  useEffect(() => {
    if (report) seen = { companyId: company.id, metals: metalsOf(report) };
  }, [report, company.id]);
  const inUse = report ? metalsOf(report) : seen?.companyId === company.id ? seen.metals : [];
  // The switch shows only when the books hold more than one metal (or this one is not among them).
  const metals = METALS.filter((m) => m === metal || inUse.includes(m));

  return (
    <Page
      title="Stock"
      right={
        metals.length > 1 ? (
          <span className="stock-metal">
            <Segmented
              variant="metal"
              label="Metal"
              value={metal}
              onChange={(next) => navigate({ name: "stock", metal: next }, { replace: true })}
              options={metals.map((m) => ({ value: m, label: LABEL[m] }))}
            />
          </span>
        ) : undefined
      }
    >
      <div className="stock-screen" aria-busy={loading}>
        {error ? (
          <Notice
            tone="error"
            action={
              <Button size="sm" variant="soft" onClick={reload}>
                Retry
              </Button>
            }
          >
            Could not load the stock: {error}
          </Notice>
        ) : null}

        {report ? (
          <StockTotal fine={cardValue(report, "Closing")} />
        ) : !error ? (
          <div className="stock-skeleton" role="status" aria-label="Loading stock">
            <Skeleton height={96} radius={18} />
            <Skeleton height={72} radius={14} />
            <Skeleton height={72} radius={14} />
          </div>
        ) : null}

        <CheckList items={warnings} />

        {report && items.length === 0 && !noStock ? (
          <Notice>
            {report.tables[2]
              ? "Only the opening stock so far — items show here once this year's bills are entered."
              : "Item-wise stock needs the latest server: this one lists only the items that went out, and none have yet."}
          </Notice>
        ) : null}

        {noStock && items.length === 0 ? (
          <EmptyState
            icon="cube"
            title={`No ${metal} entries yet`}
            action={
              <>
                <Button variant="soft" icon="cart" onClick={() => navigate({ name: "entry", kind: "purchase" })}>
                  Purchase entry
                </Button>
                <Button variant="plain" icon="trend" onClick={() => navigate({ name: "entry", kind: "sale" })}>
                  Sales entry
                </Button>
              </>
            }
          >
            Pehle Sales ya Purchase entries daalo — stock yahan apne aap calculate hoga.
          </EmptyState>
        ) : null}

        {items.length > 0 ? (
          <section className="stock-list" aria-label="Stock by item">
            {items.map((row, i) => (
              <ItemCard key={`${row.item}-${i}`} row={row} />
            ))}
          </section>
        ) : null}
      </div>
    </Page>
  );
}
