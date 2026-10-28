import { formatPaise } from "../../format";
import type { Preview } from "./calc";

/** The violet total box: the rupees billed (labour + diamond). */
export function TotalPanel({ figures: f }: { figures: Preview }) {
  return (
    <div className="entry-total">
      <p className="entry-total__label">Total amount</p>
      <p className="entry-total__amount">{formatPaise(f.total, 0)}</p>
      {f.roundOff ? <p className="entry-total__line">Includes round off {formatPaise(f.roundOff, 2, true)}</p> : null}
    </div>
  );
}
