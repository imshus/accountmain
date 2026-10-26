import { useMemo } from "react";
import { useBooks } from "../../books";
import { useSession } from "../../session";
import type { VoucherRow, VoucherType } from "../../types";
import { useBooksReport } from "./useBooksReport";

/**
 * The bill total of an entry in the voucher list. The list's `amount` is the sum of the debit lines, so a round-off
 * posted on the debit side is counted in it (INV … 10,837.15 for a ₹10,837 bill). The Round Off ledger's own lines
 * say on which side and how much, so the party's figure can be worked out exactly from one report.
 */

export const ROUND_OFF = "Round Off";

// The party is debited on these (a sale, a purchase return) and credited on the others.
const PARTY_DEBITED = new Set<VoucherType>(["Sales", "Debit Note"]);
const PARTY_CREDITED = new Set<VoucherType>(["Purchase", "Credit Note"]);

/** Round-off per entry, in paise (+ = Dr), keyed by billKey. */
export type RoundOffs = Map<string, number>;

const billKey = (date: string, vtype: string, number: string) => `${date}|${vtype}|${number}`;

export function billPaise(v: VoucherRow, roundOffs: RoundOffs | null): number {
  if (!v.ledgers.includes(ROUND_OFF) || (!PARTY_DEBITED.has(v.vtype) && !PARTY_CREDITED.has(v.vtype))) return v.amount;
  const ro = roundOffs?.get(billKey(v.date, v.vtype, v.number));
  if (ro === undefined) {
    // Not in the report (a cancelled entry, or the report has not loaded): a rounded bill is whole rupees, and the
    // round-off is under a rupee, so the bill is the list amount without its paise.
    return Math.floor(v.amount / 100) * 100;
  }
  // Party Dr: a Dr round-off is added to the debit side. Party Cr: the debits are the bill plus a Cr round-off.
  return PARTY_DEBITED.has(v.vtype) ? v.amount - Math.max(ro, 0) : v.amount + Math.min(ro, 0);
}

type LedgerRow = { type?: unknown; number?: unknown; date?: unknown; debit?: unknown; credit?: unknown };

/** The Round Off ledger's entries since the books began (one report, cached with the others). */
export function useRoundOffs(): RoundOffs | null {
  const { company } = useSession();
  const { ledgers } = useBooks();
  const id = ledgers.find((l) => l.name === ROUND_OFF)?.id;
  const { report } = useBooksReport("ledger", { ledger_id: String(id ?? ""), start: company?.fy_start ?? "" }, Boolean(id && company));
  return useMemo(() => {
    if (!report) return null;
    const map: RoundOffs = new Map();
    for (const row of (report.tables[0]?.rows ?? []) as LedgerRow[]) {
      if (typeof row.number !== "string" || typeof row.type !== "string" || typeof row.date !== "string") continue;
      const paise = Math.round((Number(row.debit) || 0) * 100) - Math.round((Number(row.credit) || 0) * 100);
      const key = billKey(row.date, row.type, row.number);
      map.set(key, (map.get(key) ?? 0) + paise);
    }
    return map;
  }, [report]);
}

/** The entries with `amount` set to the bill total. */
export function useBillTotals(rows: VoucherRow[]): VoucherRow[] {
  const roundOffs = useRoundOffs();
  return useMemo(
    () => rows.map((v) => {
      const bill = billPaise(v, roundOffs);
      return bill === v.amount ? v : { ...v, amount: bill };
    }),
    [rows, roundOffs],
  );
}
