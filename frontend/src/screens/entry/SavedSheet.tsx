import { formatDMY, formatMg } from "../../format";
import type { EntryKind } from "../../router";
import type { Metal, VoucherDetail } from "../../types";
import { Button, Icon, Sheet } from "../../ui";
import { money } from "./money";

export type SavedBill = {
  voucher: VoucherDetail;
  party: string;
  metal: Metal;
  settle: "Wt" | "Rs";
  /** What the screen showed before saving, to compare with what the books posted. */
  shown: { total: number; fineMg: number };
};

const num = (value: unknown) => (typeof value === "number" ? value : 0);

/** After Save: the number the books gave the bill, its total and fine metal, and whether they match the preview. */
export function SavedSheet({ saved, kind, onNew, onDone }: { saved: SavedBill | null; kind: EntryKind; onNew: () => void; onDone: () => void }) {
  const sale = kind === "sale";
  const summary = saved?.voucher.summary ?? {};
  const total = num(summary.total);
  const fine = num(summary.fine_by_weight_mg) + num(summary.fine_in_rupees_mg);
  const matches = saved ? total === saved.shown.total && fine === saved.shown.fineMg : true;
  return (
    <Sheet
      open={saved !== null}
      onClose={onDone}
      title={sale ? "Sale saved" : "Purchase saved"}
      description={saved ? `${saved.voucher.number} · ${formatDMY(saved.voucher.date)} · ${saved.party}` : undefined}
      actions={
        <>
          <Button variant="plain" onClick={onNew}>
            {sale ? "New sale" : "New purchase"}
          </Button>
          <Button variant="brand" onClick={onDone} data-autofocus>
            See in Transactions
          </Button>
        </>
      }
    >
      {saved ? (
        <>
          <dl className="entry-saved">
          <div>
            <dt>Invoice no</dt>
            <dd>{saved.voucher.number}</dd>
          </div>
          <div>
            <dt>Total amount</dt>
            <dd>{money(total)}</dd>
          </div>
          <div>
            <dt>Fine {saved.metal}</dt>
            <dd className="entry-saved__gold">{formatMg(fine)}</dd>
          </div>
        </dl>
          <p className={`entry-saved__check${matches ? "" : " is-off"}`}>
            <Icon name={matches ? "check" : "alert"} size={16} stroke={2.2} />
            {matches
              ? "Every figure matches the preview"
              : `The books worked out ${money(total)} and ${formatMg(fine)}; the screen showed ${money(saved.shown.total)} and ${formatMg(saved.shown.fineMg)}. The books' figures are the ones saved.`}
          </p>
          {saved.settle === "Wt" && fine ? (
            <p className="entry-saved__owe">
              {sale
                ? `${saved.party} owes ${formatMg(fine)} fine ${saved.metal} (by weight)`
                : `You owe ${saved.party} ${formatMg(fine)} fine ${saved.metal} (by weight)`}
            </p>
          ) : null}
        </>
      ) : null}
    </Sheet>
  );
}
