import type { Ledger, VoucherRow, VoucherType } from "../../../types";
import type { IconName } from "../../../ui";
import { utcDay } from "../figures";

/** The grey icon of each kind of entry (the owner's picture): an arrow down for money in, a file for purchase bills. */
export const KIND_LOOK: Record<VoucherType, IconName> = {
  Sales: "income",
  Purchase: "file",
  Receipt: "income",
  Payment: "coins",
  "Credit Note": "swap",
  "Debit Note": "income",
  "Metal Receipt": "diamond",
  "Metal Issue": "diamond",
  Journal: "book",
  Contra: "swap",
};

/** The type as the cards say it: "Purchases", else the voucher type ("Sales", "Receipt", "Journal", ...). */
export const typeLabel = (vtype: VoucherType): string => (vtype === "Purchase" ? "Purchases" : vtype);

// Money coming in (sales, receipts, purchase returns) shows mint with "+"; going out rose with "−".
const INFLOW = new Set<VoucherType>(["Sales", "Receipt", "Debit Note"]);
const OUTFLOW = new Set<VoucherType>(["Purchase", "Payment", "Credit Note"]);
export const flowOf = (v: VoucherRow): "in" | "out" | "none" => (INFLOW.has(v.vtype) ? "in" : OUTFLOW.has(v.vtype) ? "out" : "none");

/** The customer / supplier on an entry; the other ledgers are Sales, GST, Gold Stock and the like. */
export function partyNamesOf(ledgers: Ledger[]): Set<string> {
  return new Set(ledgers.filter((l) => l.group_name.startsWith("Sundry")).map((l) => l.name));
}

export function partyOf(v: VoucherRow, parties: Set<string>): string {
  return v.ledgers.find((n) => parties.has(n)) ?? v.ledgers[0] ?? v.vtype;
}

/** The name on an entry's card: its party, else its first ledger ("Rent", "Cash"), as its details say; with no ledger,
 * its narration, else its type. */
export function nameOf(v: VoucherRow, parties: Set<string>): string {
  return v.ledgers.length ? partyOf(v, parties) : v.narration?.trim() || typeLabel(v.vtype);
}

const DAY_MS = 86_400_000;
const dayMonth = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const dayMonthYear = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** When an entry was made, as the cards say it: "Today", "Yesterday", "4 Aug" ("4 Aug 2025" in another year). Bills
 * carry a date, not a time. */
export function whenOf(date: string, today: string): string {
  const day = utcDay(date);
  if (!Number.isFinite(day)) return date;
  const ago = Math.round((utcDay(today) - day) / DAY_MS);
  if (ago === 0) return "Today";
  if (ago === 1) return "Yesterday";
  return (date.slice(0, 4) === today.slice(0, 4) ? dayMonth : dayMonthYear).format(day);
}

/** Search by party, number, any ledger on it or the narration (e.g. the salesman). */
export function matches(v: VoucherRow, party: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return [party, v.number, v.narration ?? "", v.reference ?? "", ...v.ledgers].some((text) => text.toLowerCase().includes(q));
}

/** Entries arrive newest first, so one pass groups them by day. */
export function byDay(rows: VoucherRow[]): { date: string; rows: VoucherRow[] }[] {
  const days: { date: string; rows: VoucherRow[] }[] = [];
  for (const v of rows) {
    const last = days[days.length - 1];
    if (last && last.date === v.date) last.rows.push(v);
    else days.push({ date: v.date, rows: [v] });
  }
  return days;
}
