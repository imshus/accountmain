import { useEffect, useState } from "react";
import { formatDay, formatMg } from "../../../format";
import { navigate } from "../../../router";
import type { VoucherRow } from "../../../types";
import { Button, Notice, Sheet } from "../../../ui";
import { voucherRupees } from "../figures";
import { flowOf } from "./vouchers";
import "./txn.css";

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
  useEffect(() => {
    setError(null);
    setBusy(false);
  }, [id, mode]);

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
    </Sheet>
  );
}
