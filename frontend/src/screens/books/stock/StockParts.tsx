import type { Report } from "../../../types";
import { Box } from "../../../ui";
import { weightShort } from "../figures";
import "./stock.css";

/** One item's stock: net and fine grams (in − out), diamonds in carats (in − out), net grams in and out. */
export type StockItem = { item: string; net_in: number; net_out: number; net: number; fine: number; dia: number };

const NEGATIVE = -0.0005;
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
const nameOf = (value: unknown) => (typeof value === "string" && value.trim() ? value.trim() : "Item not named");

/**
 * The report's "By item" table, in the server's order (largest fine first). An older server has no such table: its
 * "Items that went out" show instead, one card per item, as stock that only left (nothing came in).
 */
export function stockItems(report: Report | null): StockItem[] {
  if (!report) return [];
  const byItem = report.tables[2];
  if (byItem) {
    return byItem.rows.map((row) => ({
      item: nameOf(row.item),
      net_in: num(row.net_in),
      net_out: num(row.net_out),
      net: num(row.net),
      fine: num(row.fine),
      dia: num(row.dia),
    }));
  }
  // The old table has a row per item and karat: one card per item.
  const items = new Map<string, StockItem>();
  for (const row of report.tables[1]?.rows ?? []) {
    const item = nameOf(row.item);
    const seen = items.get(item) ?? { item, net_in: 0, net_out: 0, net: 0, fine: 0, dia: 0 };
    items.set(item, { ...seen, net_out: seen.net_out + num(row.net), net: seen.net - num(row.net), fine: seen.fine - num(row.fine), dia: seen.dia - num(row.dia) });
  }
  return [...items.values()].sort((a, b) => Math.abs(b.fine) - Math.abs(a.fine));
}

/** "Total fine stock": the report's closing fine balance. */
export function StockTotal({ fine }: { fine: number }) {
  return (
    <Box variant="hero" as="section" className="stock-total" aria-label="Total fine stock">
      <p className="stock-total__label">Total fine stock</p>
      <p className={`stock-total__value${fine < NEGATIVE ? " is-negative" : ""}`}>{weightShort(fine)}</p>
    </Box>
  );
}

/** One item: its net weight (mint, rose below zero), then fine, diamonds and what came in / went out. */
export function ItemCard({ row }: { row: StockItem }) {
  const bits = [`Fine ${weightShort(row.fine)}`];
  if (Math.abs(row.dia) >= 0.0005) bits.push(`Diamond ${weightShort(row.dia, "ct")}`);
  bits.push(`In ${weightShort(row.net_in)} / Out ${weightShort(row.net_out)}`);
  return (
    <Box className="stock-item">
      <div className="stock-item__head">
        <span>{row.item}</span>
        <strong className={row.net < NEGATIVE ? "stock-out" : "stock-in"}>{weightShort(row.net)} net</strong>
      </div>
      <p className="stock-item__line">{bits.join(" · ")}</p>
    </Box>
  );
}
