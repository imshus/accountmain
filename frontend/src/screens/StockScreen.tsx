import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBooks } from "../books";
import { formatDMY, formatMg, formatPaise } from "../format";
import type { StockMetal } from "../router";
import { navigate } from "../router";
import { useCompany } from "../session";
import type { StockItem } from "../types";
import { Box, Button, Card, EmptyState, Field, FieldRow, Input, Notice, Page, Sheet, Skeleton } from "../ui";
import { purityText } from "./books/txn/billDetails";
import "./entry/entry.css";
import "./StockScreen.css";

export type StockScreenProps = { metal: StockMetal };

const money = (paise: number) => formatPaise(paise, paise % 100 ? 2 : 0);
const grams = (mg: number | null | undefined) => (mg ? formatMg(mg) : null);
const carats = (mct: number | null | undefined) => (mct ? `${(mct / 1000).toFixed(3)} ct` : null);
const rupees = (paise: number | null | undefined) => (paise ? money(paise) : null);
const TYPE: Record<string, string> = { Sales: "Sales", Purchase: "Purchase", "Credit Note": "Sales return", "Debit Note": "Purchase return" };

/** Rows of a detail card: [label, value]; a value left out shows "—", as in the design. */
function Rows({ rows }: { rows: [string, string | null | undefined][] }) {
  return (
    <dl className="entry-totals">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/** One item opened: the design's Entry, Item, Gold, Diamond, Color Stone, Labour and Total cards. */
function ItemSheet({ item, onClose }: { item: StockItem | null; onClose: () => void }) {
  return (
    <Sheet open={item !== null} onClose={onClose} title={item?.item || "Item"} description={item ? `${item.number} · ${formatDMY(item.date)}` : undefined}>
      {item ? (
        <div className="stock-detail">
          <Card title="Entry">
            <Rows rows={[["Type", TYPE[item.vtype] ?? item.vtype], ["Date", formatDMY(item.date)], ["Invoice", item.number], ["Party", item.party]]} />
          </Card>
          <Card title="Item">
            <Rows rows={[["Item name", item.item], ["Jewell code", item.tag_no], ["Design no.", item.design_no]]} />
          </Card>
          <Card title="Gold">
            <Rows rows={[["Gross weight", grams(item.gross_mg)], ["Net weight", grams(item.net_mg)],
              ["Purity %", item.tunch_bp ? purityText(null, item.tunch_bp) : null], ["Karat", item.purity], ["Fine weight", grams(item.fine_mg)]]} />
          </Card>
          <Card title="Diamond">
            <Rows rows={[["Shape", item.dia_shape], ["Value", rupees(item.dia_paise)], ["Color", item.colour], ["Clarity", item.clarity],
              ["Weight", carats(item.dia_mct)]]} />
          </Card>
          <Card title="Color Stone">
            <Rows rows={[["Shape", item.stn_shape], ["Value", rupees(item.stn_paise)], ["Color", item.stn_colour], ["Clarity", item.stn_clarity],
              ["Weight", carats(item.stn_mct)]]} />
          </Card>
          <Card title="Labour">
            <Rows rows={[["Labour value", rupees(item.labour_paise)]]} />
          </Card>
          <Card title="Total">
            <Rows rows={[["Total Amount", item.amount_paise ? money(item.amount_paise) : null]]} />
          </Card>
        </div>
      ) : null}
    </Sheet>
  );
}

/** Stock (design: accounts-ai-design-mockup, Stock): the totals of the items in the period, the From / To dates, and every
 * item of the Sales and Purchase bills; tap one for all its details. */
export default function StockScreen(_props: StockScreenProps) {
  const company = useCompany();
  const { version } = useBooks();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [rows, setRows] = useState<StockItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState<StockItem | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    api
      .stockItems(company.id, from, to)
      .then((answer) => live && setRows(answer.rows))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [company.id, from, to, version, attempt]);

  const totals = useMemo(() => {
    const sum = (pick: (r: StockItem) => number | null | undefined) => (rows ?? []).reduce((n, r) => n + (pick(r) ?? 0), 0);
    return [
      ["Total Gross Weight", grams(sum((r) => r.gross_mg))],
      ["Total Net Weight", grams(sum((r) => r.net_mg))],
      ["Total Diamond Weight", carats(sum((r) => r.dia_mct))],
      ["Total Diamond Value", rupees(sum((r) => r.dia_paise))],
      ["Total Labour Amount", rupees(sum((r) => r.labour_paise))],
      ["Total Amount", rupees(sum((r) => r.amount_paise))],
    ] as [string, string | null][];
  }, [rows]);

  return (
    <Page title="Stock">
      <div className="entry stock-page" aria-busy={rows === null && !error}>
        {error ? (
          <Notice tone="error" action={<Button size="sm" variant="soft" onClick={() => setAttempt((n) => n + 1)}>Retry</Button>}>
            Could not load the stock: {error}
          </Notice>
        ) : null}

        <Card title="Total">
          <Rows rows={totals} />
        </Card>

        <Card>
          <FieldRow>
            <Field label="From" htmlFor="stock-from">
              <Input id="stock-from" type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} />
            </Field>
            <Field label="To" htmlFor="stock-to">
              <Input id="stock-to" type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} />
            </Field>
          </FieldRow>
        </Card>

        {rows === null && !error ? (
          <div className="stock-page__list" role="status" aria-label="Loading stock">
            <Skeleton height={70} radius={18} />
            <Skeleton height={70} radius={18} />
          </div>
        ) : null}

        {rows && rows.length === 0 ? (
          <EmptyState
            icon="cube"
            title={from || to ? "No items in these dates" : "No items yet"}
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
            Sales ya Purchase entries daalo — har item yahan dikhega.
          </EmptyState>
        ) : null}

        {rows && rows.length ? (
          <ul className="stock-page__list" aria-label="Items">
            {rows.map((row, i) => (
              <Box as="li" key={`${row.voucher_id}-${i}`} className="stock-row">
                <button type="button" className="stock-row__btn" onClick={() => setOpen(row)}>
                  <span className="stock-row__top">
                    <b>{row.item || row.tag_no || "Item"}</b>
                    <b className="stock-row__amt">{row.amount_paise ? money(row.amount_paise) : grams(row.net_mg) ?? "—"}</b>
                  </span>
                  <small>{row.party || "—"}</small>
                </button>
              </Box>
            ))}
          </ul>
        ) : null}
      </div>
      <ItemSheet item={open} onClose={() => setOpen(null)} />
    </Page>
  );
}
