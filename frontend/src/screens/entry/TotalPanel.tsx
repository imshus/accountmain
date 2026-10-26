import { formatPaise, formatRupees } from "../../format";
import { readAmount } from "../../components/accounts/shared";
import type { Preview } from "./calc";
import type { EntryForm } from "./form";
import { grams } from "./money";

/** The violet total box: the rupees billed and where the fine metal goes. */
export function TotalPanel({ figures: f, form, sale }: { figures: Preview; form: EntryForm; sale: boolean }) {
  const metal = form.metal;
  const rate = readAmount(form.metalRate);
  const line = !f.fineMg
    ? `Enter the weight and purity to see the fine ${metal}`
    : form.settle === "Wt"
      ? sale
        ? `Customer owes ${grams(f.fineMg)} fine ${metal} (by weight)`
        : `You owe the supplier ${grams(f.fineMg)} fine ${metal} (by weight)`
      : `${grams(f.fineMg)} fine ${metal} ${sale ? "billed" : "paid for"} at ${formatRupees(Number.isFinite(rate) ? rate : 0, rate % 1 ? 2 : 0)}/g`;
  return (
    <div className="entry-total">
      <p className="entry-total__label">Total amount</p>
      <p className="entry-total__amount">{formatPaise(f.total, 0)}</p>
      <p className="entry-total__line">{line}</p>
      {f.roundOff ? <p className="entry-total__line">Includes round off {formatPaise(f.roundOff, 2, true)}</p> : null}
    </div>
  );
}
