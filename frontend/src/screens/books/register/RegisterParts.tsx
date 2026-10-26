import { memo } from "react";
import type { VoucherRow, VoucherType } from "../../../types";
import { voucherRupees, weightShort } from "../figures";
import "./register.css";

// A return takes its bill off the register's totals: a credit note in Sales, a debit note in Purchase.
const RETURNS = new Set<VoucherType>(["Credit Note", "Debit Note"]);
const isReturn = (v: VoucherRow) => RETURNS.has(v.vtype);

/** The bills' amount in paise and net weight in milligrams (null when no bill has a weight). */
export function registerTotals(bills: VoucherRow[]): { paise: number; mg: number | null } {
  let paise = 0;
  let mg: number | null = null;
  for (const v of bills) {
    const sign = isReturn(v) ? -1 : 1;
    paise += sign * v.amount;
    if (typeof v.net_mg === "number") mg = (mg ?? 0) + sign * v.net_mg;
  }
  return { paise, mg };
}

/** "Ring, Chain · 12 g": the bill's items and net weight, either alone; its number when the server sends neither. */
function billLine(v: VoucherRow): string {
  const items = (v.items ?? []).filter((name) => typeof name === "string" && name.trim()).join(", ");
  const weight = v.net_mg ? weightShort(v.net_mg / 1000) : "";
  const line = [items, weight].filter(Boolean).join(" · ") || v.number;
  return isReturn(v) ? `Return · ${line}` : line;
}

/** Amount and Net weight, side by side. */
export function RegisterStats({ paise, mg }: { paise: number; mg: number | null }) {
  return (
    <dl className="reg-stats">
      <div className="reg-stat">
        <dt>Amount</dt>
        <dd>{voucherRupees(paise, paise < 0 ? "−" : "")}</dd>
      </div>
      <div className="reg-stat">
        <dt>Net weight</dt>
        <dd>{mg === null ? "—" : weightShort(mg / 1000)}</dd>
      </div>
    </dl>
  );
}

/** One bill in its day's card: party, "items · weight", amount. Tap: the bill's details. */
export const RegisterRow = memo(function RegisterRow({ bill, party, onOpen }: { bill: VoucherRow; party: string; onOpen: (bill: VoucherRow) => void }) {
  return (
    <li className="reg-row">
      <button type="button" className="reg-row__btn" onClick={() => onOpen(bill)}>
        <span className="reg-row__text">
          <strong className="reg-row__party">{party}</strong>
          <span className="reg-row__sub">{billLine(bill)}</span>
        </span>
        <strong className="reg-row__amt">{voucherRupees(bill.amount, isReturn(bill) && bill.amount ? "−" : "")}</strong>
      </button>
    </li>
  );
});
