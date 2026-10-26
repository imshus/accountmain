import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { formatCount, formatGrams, formatValue } from "../../format";
import type { Company, VoucherDetail, VoucherRow } from "../../types";
import { useBillTotals } from "../../screens/books/billTotal";
import { Button, Sheet, Spinner } from "../../ui";

type Props = {
  company: Company;
  voucherTypes: string[];
  refreshKey: number;
  onChanged: () => void;
};

const PAGE = 50;

/** Every voucher, newest first, with filters; open one to see its lines and bills, or cancel it. */
const NO_ROWS: VoucherRow[] = [];

export default function VouchersPanel({ company, voucherTypes, refreshKey, onChanged }: Props) {
  const [filters, setFilters] = useState({ vtype: "", start: "", end: "", search: "" });
  const [applied, setApplied] = useState(filters);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<{ total: number; rows: VoucherRow[] } | null>(null);
  const [open, setOpen] = useState<VoucherDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The voucher waiting for "Cancel voucher" in the confirm sheet.
  const [doomed, setDoomed] = useState<VoucherDetail | null>(null);
  // The list's amount counts a debit round-off; show the bill total, as the invoice and the party's balance do.
  const rows = useBillTotals(page?.rows ?? NO_ROWS);
  const showFine = Boolean(page?.rows.some((r) => r.fine_mg));

  const load = useCallback(async () => {
    setError(null);
    try {
      setPage(await api.vouchers(company.id, { ...applied, offset: String(offset), limit: String(PAGE) }));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [company.id, applied, offset]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function show(id: number) {
    if (open?.id === id) return setOpen(null);
    try {
      setOpen(await api.voucher(company.id, id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function cancel(voucher: VoucherDetail) {
    setDoomed(null);
    try {
      await api.cancelVoucher(company.id, voucher.id);
      setOpen(await api.voucher(company.id, voucher.id));
      onChanged();
      void load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <h2>Vouchers</h2>
      <form
        className="report-params"
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setApplied(filters);
        }}
      >
        <label className="field">
          <span>Type</span>
          <select value={filters.vtype} onChange={(e) => setFilters((f) => ({ ...f, vtype: e.target.value }))}>
            <option value="">All</option>
            {voucherTypes.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>From</span>
          <input type="date" value={filters.start} onChange={(e) => setFilters((f) => ({ ...f, start: e.target.value }))} />
        </label>
        <label className="field">
          <span>To</span>
          <input type="date" value={filters.end} onChange={(e) => setFilters((f) => ({ ...f, end: e.target.value }))} />
        </label>
        <label className="field grow">
          <span>Search number, ledger, narration, cheque no.</span>
          <input value={filters.search} onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))} />
        </label>
        <button className="button primary" type="submit">
          Show
        </button>
      </form>
      {error ? <div className="callout warning">{error}</div> : null}
      {page ? (
        <>
          <p className="muted small">
            {formatCount(page.total)} voucher{page.total === 1 ? "" : "s"}
            {page.total > PAGE ? ` · showing ${offset + 1}–${Math.min(offset + PAGE, page.total)}` : ""}
          </p>
          <div className="table-scroll">
            <table className="data-table compact clickable">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>No.</th>
                  <th>Ledgers</th>
                  <th>Reference</th>
                  <th className="num">Amount</th>
                  {showFine ? <th className="num">Metal (fine)</th> : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((v) => (
                  <VoucherRowView key={v.id} voucher={v} showFine={showFine} open={open?.id === v.id ? open : null} onToggle={() => void show(v.id)} onCancel={setDoomed} />
                ))}
              </tbody>
            </table>
          </div>
          {page.total > PAGE ? (
            <div className="sql-actions">
              <button className="button small-button" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
                ← Newer
              </button>
              <button className="button small-button" disabled={offset + PAGE >= page.total} onClick={() => setOffset((o) => o + PAGE)}>
                Older →
              </button>
            </div>
          ) : null}
        </>
      ) : error ? null : (
        <Spinner>Loading vouchers…</Spinner>
      )}
      <Sheet
        open={doomed !== null}
        onClose={() => setDoomed(null)}
        title={doomed ? `Cancel ${doomed.vtype} ${doomed.number}?` : "Cancel voucher?"}
        description="It stays in the list marked cancelled and stops counting in every report; the audit trail records the change."
        actions={
          <>
            <Button onClick={() => setDoomed(null)} data-autofocus>
              Keep it
            </Button>
            <Button variant="danger" onClick={() => doomed && void cancel(doomed)}>
              Cancel voucher
            </Button>
          </>
        }
      />
    </section>
  );
}

function VoucherRowView({ voucher, showFine, open, onToggle, onCancel }: {
  voucher: VoucherRow;
  showFine: boolean;
  open: VoucherDetail | null;
  onToggle: () => void;
  onCancel: (voucher: VoucherDetail) => void;
}) {
  return (
    <>
      {/* The row still opens on a click or tap; the number is a real button for keyboard and screen-reader users. */}
      <tr className={voucher.cancelled ? "row-cancelled" : undefined} onClick={onToggle}>
        <td>{formatValue(voucher.date, "date")}</td>
        <td>{voucher.vtype}</td>
        <td>
          <button
            type="button"
            className="link-button"
            style={{ fontSize: "inherit" }}
            aria-expanded={Boolean(open)}
            aria-controls={open ? `voucher-${voucher.id}` : undefined}
            aria-label={`${voucher.vtype} ${voucher.number}, lines and bills`}
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
          >
            {voucher.number}
          </button>
        </td>
        <td className="wrap">{voucher.cancelled ? "Cancelled" : voucher.ledgers.join(", ")}</td>
        <td>{voucher.reference || ""}</td>
        <td className="num">{voucher.amount ? formatValue(voucher.amount / 100, "money") : ""}</td>
        {showFine ? <td className="num">{voucher.fine_mg ? formatGrams(voucher.fine_mg / 1000) : ""}</td> : null}
      </tr>
      {open ? (
        <tr className="row-detail" id={`voucher-${voucher.id}`}>
          <td colSpan={showFine ? 7 : 6}>
            <table className="data-table compact">
              <thead>
                <tr>
                  <th>Ledger</th>
                  <th className="num">Debit</th>
                  <th className="num">Credit</th>
                  <th>Bill-wise</th>
                </tr>
              </thead>
              <tbody>
                {open.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{line.ledger}</td>
                    <td className="num">{line.dr_paise ? formatValue(line.dr_paise / 100, "money") : ""}</td>
                    <td className="num">{line.cr_paise ? formatValue(line.cr_paise / 100, "money") : ""}</td>
                    <td className="small">
                      {line.bills
                        .map((b) => `${BILL_KIND[b.kind] ?? b.kind}${b.bill_ref ? ` ${b.bill_ref}` : ""} ${formatValue(Math.abs(b.amount_paise) / 100, "money")}${b.due_date ? `, due ${formatValue(b.due_date, "date")}` : ""}`)
                        .join("; ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {open.metal_lines.length ? <MetalLines voucher={open} /> : null}
            <p className="muted small">
              {open.narration ? `Narration: ${open.narration}. ` : ""}
              {open.source?.startsWith("import:") ? "Imported from an uploaded register. " : ""}
              {open.cancelled ? "This voucher is cancelled." : ""}
            </p>
            {!open.cancelled ? (
              <button className="button small-button danger-button" onClick={() => onCancel(open)}>
                Cancel voucher
              </button>
            ) : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}

function MetalLines({ voucher }: { voucher: VoucherDetail }) {
  const g = (mg: number | null) => (mg ? formatGrams(mg / 1000) : "");
  return (
    <table className="data-table compact">
      <thead>
        <tr>
          <th>Metal account</th>
          <th>Item</th>
          <th className="num">Gross</th>
          <th className="num">Net</th>
          <th className="num">Tunch</th>
          <th className="num">Dr (fine)</th>
          <th className="num">Cr (fine)</th>
        </tr>
      </thead>
      <tbody>
        {voucher.metal_lines.map((m) => (
          <tr key={m.id}>
            <td>
              {m.ledger} <span className="muted small">{m.metal}</span>
            </td>
            <td>{[m.item, m.purity, m.tag_no].filter(Boolean).join(" · ")}</td>
            <td className="num">{g(m.gross_mg)}</td>
            <td className="num">{g(m.net_mg)}</td>
            <td className="num">{m.tunch_bp ? `${m.tunch_bp / 100}` : ""}</td>
            <td className="num">{g(m.dr_mg)}</td>
            <td className="num">{g(m.cr_mg)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const BILL_KIND: Record<string, string> = { new: "New Ref", against: "Agst Ref", advance: "Advance", on_account: "On Account" };
