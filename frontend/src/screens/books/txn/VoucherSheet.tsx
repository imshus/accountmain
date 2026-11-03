import { useEffect, useState } from "react";
import { api } from "../../../api";
import { formatDay, formatMg } from "../../../format";
import { navigate } from "../../../router";
import { useSession } from "../../../session";
import type { VoucherDetail, VoucherRow } from "../../../types";
import { Button, Notice, Sheet, Skeleton } from "../../../ui";
import { voucherRupees } from "../figures";
import { billAmounts, itemLines, itemRows } from "./billDetails";
import { flowOf } from "./vouchers";
import "./txn.css";

/** The bill's items (tag, weights, purity, fine, diamonds, HUID, labour and diamond amounts) and its money lines. */
function BillParts({ detail }: { detail: { bill: VoucherDetail | null; error: string | null } | null }) {
  if (!detail) {
    return (
      <div className="txn-bill" role="status" aria-label="Loading the bill's items">
        <Skeleton height={14} width={90} />
        <Skeleton height={96} radius={12} />
      </div>
    );
  }
  if (!detail.bill) return <Notice tone="error">Could not load the bill's items: {detail.error}</Notice>;
  const items = itemLines(detail.bill);
  const money = billAmounts(detail.bill);
  if (!items.length && !money.length) return null;
  return (
    <div className="txn-bill">
      {items.length ? <h3 className="txn-bill__title">{items.length === 1 ? "Item" : `Items (${items.length})`}</h3> : null}
      {items.map((m) => (
        <section key={m.id} className="txn-item" aria-label={m.item ?? "Item"}>
          <p className="txn-item__name">
            <strong>{m.item ?? "Item"}</strong>
            {m.tag_no ? <span className="txn-item__tag">Tag {m.tag_no}</span> : null}
          </p>
          <dl className="txn-details">
            {itemRows(m).map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
      {money.length ? (
        <>
          <h3 className="txn-bill__title">Amounts</h3>
          <dl className="txn-details">
            {money.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </>
      ) : null}
    </div>
  );
}

export type SheetState = { voucher: VoucherRow; party: string; mode: "details" | "confirm" } | null;

type Props = {
  state: SheetState;
  onClose: () => void;
  onMode: (mode: "details" | "confirm") => void;
  /** Cancels the entry (books.cancel); throws with the server's message on failure. */
  onCancel: (voucher: VoucherRow) => Promise<void>;
};

/** An entry's details, and the confirm step before cancelling it. */
export function VoucherSheet({ state, onClose, onMode, onCancel }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = state?.voucher.id;
  const mode = state?.mode;
  const companyId = useSession().company?.id;
  useEffect(() => {
    setError(null);
    setBusy(false);
  }, [id, mode]);

  // The whole bill (its items with tag, weights, purity and amounts), read when its details open.
  const [detail, setDetail] = useState<{ id: number; bill: VoucherDetail | null; error: string | null } | null>(null);
  useEffect(() => {
    if (id === undefined || mode !== "details" || companyId === undefined) return;
    let live = true;
    setDetail(null);
    api.voucher(companyId, id).then(
      (bill) => live && setDetail({ id, bill, error: null }),
      (e: unknown) => live && setDetail({ id, bill: null, error: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      live = false;
    };
  }, [id, mode, companyId]);

  if (!state) return null;
  const { voucher: v, party } = state;
  const name = `${v.vtype} ${v.number}`;

  const cancel = async () => {
    setBusy(true);
    setError(null);
    try {
      await onCancel(v);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  if (state.mode === "confirm") {
    return (
      <Sheet
        key="confirm"
        open
        onClose={busy ? () => undefined : onClose}
        title={`Cancel ${name}?`}
        description="It stays in the audit trail but no longer counts in the books."
        actions={
          <>
            <Button variant="plain" onClick={onClose} disabled={busy} data-autofocus>
              Keep
            </Button>
            <Button variant="danger" onClick={cancel} busy={busy}>
              Cancel entry
            </Button>
          </>
        }
      >
        {error ? <Notice tone="error">Could not cancel: {error}</Notice> : null}
      </Sheet>
    );
  }

  const flow = flowOf(v);
  const rows: [string, string][] = [
    ["Party", party],
    ["Date", formatDay(v.date)],
    ["Type", v.vtype],
    ["Number", v.number],
  ];
  if (v.amount) rows.push(["Amount", `${voucherRupees(v.amount)}${flow === "in" ? " · money in" : flow === "out" ? " · money out" : ""}`]);
  if (v.fine_mg) rows.push(["Fine metal", formatMg(v.fine_mg)]);
  if (v.narration) rows.push(["Note", v.narration]);
  rows.push(["Status", v.cancelled ? "Cancelled · kept in the audit trail" : "Active"]);

  return (
    <Sheet
      key="details"
      open
      onClose={onClose}
      title={name}
      actions={
        <>
          <Button
            variant="plain"
            icon="book"
            onClick={() => {
              onClose();
              navigate({ name: "dashboard", tab: "vouchers" });
            }}
          >
            Open in books
          </Button>
          {v.cancelled ? null : (
            <Button variant="danger" icon="trash" onClick={() => onMode("confirm")}>
              Cancel entry
            </Button>
          )}
        </>
      }
    >
      <dl className="txn-details">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <BillParts detail={detail?.id === v.id ? detail : null} />
    </Sheet>
  );
}
