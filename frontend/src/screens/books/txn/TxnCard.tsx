import { memo } from "react";
import { formatMg } from "../../../format";
import type { VoucherRow } from "../../../types";
import { Icon } from "../../../ui";
import { voucherRupees } from "../figures";
import { useLongPress } from "./useLongPress";
import { flowOf, KIND_LOOK, typeLabel } from "./vouchers";
import "./txn.css";

type Props = {
  voucher: VoucherRow;
  /** The party, else the first ledger, the narration or the type (nameOf). */
  name: string;
  /** "Today", "Yesterday", "4 Aug" (whenOf). */
  when: string;
  /** Tap (or Enter): the entry's details, with Cancel there too. */
  onOpen: (voucher: VoucherRow) => void;
  /** Press and hold: straight to "cancel this entry?". */
  onHold: (voucher: VoucherRow) => void;
};

/** One entry (the owner's picture): grey round icon, the name, "Purchases · 4 Aug", ± rupees. Cancelled ones are
 * dashed and struck. */
export const TxnCard = memo(function TxnCard({ voucher: v, name, when, onOpen, onHold }: Props) {
  const flow = flowOf(v);
  const sign = v.cancelled || flow === "none" ? "" : flow === "in" ? "+" : "−";
  const { handlers, consumeHold } = useLongPress(() => {
    if (!v.cancelled) onHold(v);
    else onOpen(v);
  });
  // A metal-only entry has no rupees: its fine weight stands in for "₹0".
  const amount = v.amount ? voucherRupees(v.amount, sign) : v.fine_mg ? `${formatMg(v.fine_mg)} fine` : voucherRupees(0);
  const line = `${typeLabel(v.vtype)} · ${when}`;
  const spoken = [name, line, v.cancelled ? "cancelled" : "", amount, v.number].filter(Boolean).join(", ");

  return (
    <li className={`txn-card${v.cancelled ? " is-cancelled" : ""}`}>
      <button
        type="button"
        className="txn-card__main"
        aria-label={spoken}
        onClick={() => {
          if (!consumeHold()) onOpen(v);
        }}
        {...handlers}
      >
        <span className="txn-card__ico" aria-hidden="true">
          <Icon name={KIND_LOOK[v.vtype] ?? "file"} size={18} />
        </span>
        <span className="txn-card__text">
          <strong className="txn-card__party">
            <span className="txn-card__name">{name}</span>
            {v.cancelled ? <span className="txn-tag-cancel">CANCELLED</span> : null}
          </strong>
          <span className="txn-card__sub">{line}</span>
        </span>
        <strong className={`txn-card__amt txn-amt--${v.cancelled ? "void" : v.amount ? flow : "none"}`}>{amount}</strong>
      </button>
    </li>
  );
});
