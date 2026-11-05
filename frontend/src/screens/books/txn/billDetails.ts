import type { MetalLineDetail, VoucherDetail, VoucherRow } from "../../../types";
import { voucherRupees, weightShort } from "../figures";

const pct = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const carat = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 3 });
/** Diamond / stone carats from thousandths, to 3 decimals as jewellers read them: 3.158 ct. */
const ct = (mct: number) => `${carat.format(mct / 1000)} ct`;
/** The books' GST ledgers (accounts/chart.py) and its round-off ledger. */
const TAX_LEDGER = /^(?:Output|Input)\s+(?:CGST|SGST|IGST|UTGST|Cess)$/i;
const ROUND_OFF = /^Round\s*Off$/i;

/** A purity as the owner reads it: "22K · 91.6%", "84%", or the code alone. */
export function purityText(code: string | null | undefined, tunchBp: number | null | undefined): string {
  const percent = typeof tunchBp === "number" && tunchBp > 0 ? `${pct.format(tunchBp / 100)}%` : "";
  const name = (code ?? "").trim();
  // A code that is the percent itself ("84" with 84%, silver "92.5") is not said twice.
  if (percent && name && Number(name.replace(/%$/, "")) === (tunchBp ?? 0) / 100) return percent;
  return [name, percent].filter(Boolean).join(" · ");
}

/** The bill card's third line: purity, fine, diamonds and how many items, whichever the bill has. "" when none. */
export function billSummary(v: VoucherRow): string {
  const codes = v.purities ?? [];
  const tunches = v.tunch_bps ?? [];
  const purity = codes.length > 1 || tunches.length > 1 ? "Mixed purity" : purityText(codes[0], tunches[0]);
  const count = v.item_count ?? 0;
  return [
    count > 1 ? `${count} items` : "",
    purity,
    v.fine_mg ? `Fine ${weightShort(v.fine_mg / 1000)}` : "",
    v.dia_mct ? `Dia ${ct(v.dia_mct)}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

/** The lines of a bill that are its items (on the stock ledger, with item details), in bill order. */
export function itemLines(detail: VoucherDetail): MetalLineDetail[] {
  return detail.metal_lines.filter((m) => m.item || m.tag_no || m.net_mg || m.gross_mg);
}

/** One item's details, only those it has: [label, value]. */
export function itemRows(m: MetalLineDetail): [string, string][] {
  const fine = m.dr_mg || m.cr_mg;
  const rows: [string, string | false][] = [
    ["Design no.", m.design_no || false],
    ["Gross weight", Boolean(m.gross_mg) && weightShort((m.gross_mg ?? 0) / 1000)],
    ["Net weight", Boolean(m.net_mg) && weightShort((m.net_mg ?? 0) / 1000)],
    ["Purity", purityText(m.purity, m.tunch_bp) || false],
    ["Fine weight", Boolean(fine) && weightShort(fine / 1000)],
    ["Diamond weight", Boolean(m.dia_mct) && ct(m.dia_mct ?? 0)],
    ["Diamond shape", m.dia_shape || false],
    ["Colour", m.colour || false],
    ["Clarity", m.clarity || false],
    ["Stone weight", Boolean(m.stn_mct) && ct(m.stn_mct ?? 0)],
    ["Stone shape", m.stn_shape || false],
    ["Stone colour", m.stn_colour || false],
    ["Stone clarity", m.stn_clarity || false],
    ["Pieces", Boolean(m.pieces) && String(m.pieces)],
    ["HUID", m.huid || false],
    ["Labour amount", Boolean(m.labour_paise) && voucherRupees(m.labour_paise ?? 0)],
    ["Diamond amount", Boolean(m.dia_paise) && voucherRupees(m.dia_paise ?? 0)],
    ["Stone amount", Boolean(m.stn_paise) && voucherRupees(m.stn_paise ?? 0)],
    ["Metal amount", Boolean(m.metal_paise) && voucherRupees(m.metal_paise ?? 0)],
  ];
  return rows.filter((r): r is [string, string] => typeof r[1] === "string" && r[1] !== "");
}

/** The bill's money: labour, diamonds, stones and metal added up over its items (only for several items: one item shows
 * its own), then GST and round off from its ledger lines. The total is the sheet's Amount. */
export function billAmounts(detail: VoucherDetail): [string, string][] {
  const items = itemLines(detail);
  const sum = (key: "labour_paise" | "dia_paise" | "stn_paise" | "metal_paise") => items.reduce((n, m) => n + (m[key] ?? 0), 0);
  const rows: [string, number][] = [
    ["Labour", sum("labour_paise")],
    ["Diamonds", sum("dia_paise")],
    ["Stones", sum("stn_paise")],
    ["Metal", sum("metal_paise")],
  ];
  const out: [string, string][] =
    items.length > 1 ? rows.filter(([, paise]) => paise).map(([label, paise]) => [label, voucherRupees(paise)]) : [];
  // GST and round off by the books' own ledger names (a party called "GST Traders" is not a tax line).
  const sale = detail.vtype === "Sales" || detail.vtype === "Debit Note";
  for (const line of detail.lines) {
    const paise = line.cr_paise - line.dr_paise; // credit adds to a sale's total, debit to a purchase's
    if (!paise) continue;
    if (TAX_LEDGER.test(line.ledger)) out.push([line.ledger.replace(/^(?:Output|Input)\s+/i, ""), voucherRupees(Math.abs(paise))]);
    else if (ROUND_OFF.test(line.ledger)) {
      const adds = sale ? paise > 0 : paise < 0;
      out.push(["Round off", voucherRupees(Math.abs(paise), adds ? "+" : "−")]);
    }
  }
  return out;
}
