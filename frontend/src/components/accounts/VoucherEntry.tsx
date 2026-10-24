import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { formatValue } from "../../format";
import type { Company, Ledger, VoucherDetail, VoucherType } from "../../types";
import { JewelleryForm, MetalMoveForm, RateCutForm } from "./MetalEntry";
import { CASH_BANK, LedgerSelect, NumberInput, PARTIES, SavedVoucher as Saved, badNumber, parseAmount, today, useSaving } from "./shared";

type Props = {
  company: Company;
  ledgers: Ledger[];
  onSaved: (voucher: VoucherDetail) => void;
};

const KINDS = [
  { key: "invoice", title: "GST bill", hint: "Sale or purchase with GST" },
  { key: "settlement", title: "Money in / out", hint: "Payment received or made, against bills" },
  { key: "jewellery", title: "Jewellery bill", hint: "Items by weight, tunch and fine" },
  { key: "metal", title: "Gold in / out", hint: "Metal received or given" },
  { key: "ratecut", title: "Rate cut", hint: "Turn metal owed into rupees" },
  { key: "lines", title: "Other entry", hint: "Journal, contra, any voucher" },
] as const;
type Kind = (typeof KINDS)[number]["key"];

/** New entries: pick what happened, then fill one short form. */
export default function VoucherEntry({ company, ledgers, onSaved }: Props) {
  const [kind, setKind] = useState<Kind>("invoice");
  const props = { company, ledgers, onSaved };
  return (
    <section className="panel">
      <h2>What do you want to enter?</h2>
      <div className="kind-grid" role="tablist">
        {KINDS.map((k) => (
          <button key={k.key} role="tab" aria-selected={kind === k.key} className={`kind-tile${kind === k.key ? " active" : ""}`} onClick={() => setKind(k.key)}>
            <strong>{k.title}</strong>
            <span>{k.hint}</span>
          </button>
        ))}
      </div>
      {kind === "invoice" ? <InvoiceForm {...props} /> : null}
      {kind === "settlement" ? <SettlementForm {...props} /> : null}
      {kind === "jewellery" ? <JewelleryForm {...props} /> : null}
      {kind === "metal" ? <MetalMoveForm {...props} /> : null}
      {kind === "ratecut" ? <RateCutForm {...props} /> : null}
      {kind === "lines" ? <LinesForm {...props} /> : null}
    </section>
  );
}

function InvoiceForm({ company, ledgers, onSaved }: Props) {
  const [vtype, setVtype] = useState<VoucherType>("Sales");
  const [date, setDate] = useState(today());
  const [number, setNumber] = useState("");
  const [reference, setReference] = useState("");
  const [party, setParty] = useState("");
  const [items, setItems] = useState([{ ledger: "", taxable: "", rate: "18" }]);
  const [roundOff, setRoundOff] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<VoucherDetail | null>(null);
  const [saving, guard] = useSaving();
  const sales = vtype === "Sales" || vtype === "Credit Note";
  const partyGroup = sales ? "Sundry Debtors" : "Sundry Creditors";
  const itemGroup = sales ? "Sales Accounts" : "Purchase Accounts";
  const partyLedger = ledgers.find((l) => String(l.id) === party);
  const inter = Boolean(partyLedger?.state_code && company.state_code && partyLedger.state_code !== company.state_code);
  const taxable = items.reduce((s, i) => s + parseAmount(i.taxable), 0);
  const tax = items.reduce((s, i) => s + (parseAmount(i.taxable) * Number(i.rate || 0)) / 100, 0);
  const problem = badNumber(items.map((i, n) => [items.length > 1 ? `Taxable value on line ${n + 1}` : "Taxable value", i.taxable]));
  // A customer or Sales ledger left from another Type is hidden by the filters, so it must never be posted.
  const wrongSide =
    (Boolean(party) && partyLedger?.group_name !== partyGroup) ||
    items.some((i) => i.ledger && ledgers.find((l) => String(l.id) === i.ledger)?.group_name !== itemGroup);

  function changeType(next: VoucherType) {
    if ((next === "Sales" || next === "Credit Note") !== sales) {
      setParty("");
      setItems((all) => all.map((x) => ({ ...x, ledger: "" })));
    }
    setVtype(next);
  }

  const save = () => guard(async () => {
    setError(null);
    try {
      const voucher = await api.createInvoice(company.id, {
        vtype, date, number: number || null, reference, party_id: Number(party), round_off: roundOff,
        items: items.filter((i) => i.taxable).map((i) => ({ ledger_id: i.ledger ? Number(i.ledger) : null, taxable: i.taxable, rate: Number(i.rate || 0) })),
      });
      setSaved(voucher);
      setNumber("");
      setItems([{ ledger: "", taxable: "", rate: items[0].rate }]);
      onSaved(voucher);
    } catch (e) {
      setError((e as Error).message);
    }
  });

  return (
    <div className="entry-grid">
      <div className="report-params">
        <label className="field">
          <span>Type</span>
          <select value={vtype} onChange={(e) => changeType(e.target.value as VoucherType)}>
            {["Sales", "Purchase", "Credit Note", "Debit Note"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Date</span>
          <input type="date" value={date} min={company.fy_start} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field">
          <span>{sales ? "Invoice no. (blank = next)" : "Our voucher no. (blank = next)"}</span>
          <input value={number} onChange={(e) => setNumber(e.target.value)} maxLength={16} />
        </label>
        {!sales ? (
          <label className="field">
            <span>Supplier's bill no.</span>
            <input value={reference} onChange={(e) => setReference(e.target.value)} maxLength={60} />
          </label>
        ) : null}
        <label className="field grow">
          <span>{sales ? "Customer" : "Supplier"}</span>
          <LedgerSelect ledgers={ledgers} value={party} onChange={setParty} filter={(l) => l.group_name === partyGroup} />
        </label>
      </div>
      <table className="data-table compact">
        <thead>
          <tr>
            <th>{sales ? "Sales ledger" : "Purchase ledger"}</th>
            <th className="num">Taxable value</th>
            <th className="num">GST %</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i}>
              <td>
                <LedgerSelect ledgers={ledgers} value={item.ledger} placeholder={sales ? "Sales" : "Purchase"}
                  onChange={(v) => setItems((all) => all.map((x, j) => (j === i ? { ...x, ledger: v } : x)))} filter={(l) => l.group_name === itemGroup} />
              </td>
              <td className="num">
                <NumberInput value={item.taxable} placeholder="0.00" aria-label="Taxable value"
                  onChange={(e) => setItems((all) => all.map((x, j) => (j === i ? { ...x, taxable: e.target.value } : x)))} />
              </td>
              <td className="num">
                <select value={item.rate} onChange={(e) => setItems((all) => all.map((x, j) => (j === i ? { ...x, rate: e.target.value } : x)))}>
                  {["0", "0.25", "1.5", "3", "5", "12", "18", "28", "40"].map((r) => (
                    <option key={r} value={r}>
                      {r}%
                    </option>
                  ))}
                </select>
              </td>
              <td>
                {items.length > 1 ? (
                  <button className="icon-button" onClick={() => setItems((all) => all.filter((_, j) => j !== i))} aria-label="Remove item">
                    ×
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="sql-actions">
        <button className="button small-button" onClick={() => setItems((all) => [...all, { ledger: "", taxable: "", rate: all[all.length - 1].rate }])}>
          + Add line
        </button>
        <label className="check-field">
          <input type="checkbox" checked={roundOff} onChange={(e) => setRoundOff(e.target.checked)} /> Round off to the rupee
        </label>
      </div>
      <p className="muted small">
        Taxable {formatValue(taxable, "money")} + {inter ? "IGST" : "CGST + SGST"} {formatValue(tax, "money")} ≈ {formatValue(taxable + tax, "money")}
        {party ? (inter ? " (inter-state: party's state differs from yours)" : " (intra-state)") : ""}
      </p>
      {problem ? <div className="callout warning">{problem}</div> : null}
      <button className="button primary" onClick={() => void save()} disabled={saving || !party || !taxable || Boolean(problem) || wrongSide}>
        {saving ? "Saving…" : `Save ${vtype}`}
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <Saved voucher={saved} />
    </div>
  );
}

function SettlementForm({ company, ledgers, onSaved }: Props) {
  const [vtype, setVtype] = useState<"Receipt" | "Payment">("Receipt");
  const [date, setDate] = useState(today());
  const [party, setParty] = useState("");
  const [cash, setCash] = useState("");
  const [amount, setAmount] = useState("");
  const [tds, setTds] = useState("");
  const [reference, setReference] = useState("");
  const [narration, setNarration] = useState("");
  // Pending bills with the party they belong to, so a slow answer for an earlier party is never shown for this one.
  const [loaded, setLoaded] = useState<{ key: string; bills: { bill_ref: string; pending: number; bill_date: string | null }[] }>({ key: "", bills: [] });
  const [refresh, setRefresh] = useState(0);
  const [allocate, setAllocate] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<VoucherDetail | null>(null);
  const [saving, guard] = useSaving();
  const group = vtype === "Receipt" ? "Sundry Debtors" : "Sundry Creditors";
  const key = party ? `${company.id}/${party}/${vtype}` : "";
  const bills = loaded.key === key ? loaded.bills : [];

  useEffect(() => {
    setAllocate({});
    if (!key) return;
    let live = true;
    api.pendingBills(company.id, Number(party)).then(
      (list) => live && setLoaded({ key, bills: list.filter((b) => (vtype === "Receipt" ? b.pending > 0 : b.pending < 0)) }),
      () => live && setLoaded({ key, bills: [] }),
    );
    return () => {
      live = false;
    };
    // key covers company, party and type
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, refresh]);

  const allocated = Object.values(allocate).reduce((s, v) => s + parseAmount(v), 0);
  const total = parseAmount(amount) + parseAmount(tds);
  const problem = badNumber([
    ["Amount", amount],
    ["TDS", tds],
    ...bills.map((b): [string, string] => [`Settle now for ${b.bill_ref}`, allocate[b.bill_ref] ?? ""]),
  ]);

  function changeType(next: "Receipt" | "Payment") {
    // TDS on a receipt goes to TDS Receivable, on a payment to TDS Payable: a figure typed for one is not meant for the other.
    setVtype(next);
    setParty("");
    setTds("");
    setAllocate({});
  }

  function autoAllocate() {
    let left = total;
    const next: Record<string, string> = {};
    for (const b of bills) {
      if (left <= 0) break;
      const take = Math.min(Math.abs(b.pending), left);
      next[b.bill_ref] = take.toFixed(2);
      left = Math.round((left - take) * 100) / 100;
    }
    setAllocate(next);
  }

  const save = () => guard(async () => {
    setError(null);
    try {
      const voucher = await api.createSettlement(company.id, {
        vtype, date, party_id: Number(party), cash_bank_id: Number(cash), amount, tds: tds || null, reference, narration,
        against: Object.entries(allocate)
          .filter(([ref, v]) => parseAmount(v) > 0 && bills.some((b) => b.bill_ref === ref))
          .map(([bill_ref, v]) => ({ bill_ref, amount: v })),
      });
      setSaved(voucher);
      setAmount("");
      setTds("");
      setAllocate({});
      onSaved(voucher);
      setRefresh((r) => r + 1); // reload pending bills
    } catch (e) {
      setError((e as Error).message);
    }
  });

  return (
    <div className="entry-grid">
      <div className="report-params">
        <label className="field">
          <span>Type</span>
          <select value={vtype} onChange={(e) => changeType(e.target.value as "Receipt" | "Payment")}>
            <option>Receipt</option>
            <option>Payment</option>
          </select>
        </label>
        <label className="field">
          <span>Date</span>
          <input type="date" value={date} min={company.fy_start} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field grow">
          <span>{vtype === "Receipt" ? "Received from (customer)" : "Paid to (supplier)"}</span>
          <LedgerSelect ledgers={ledgers} value={party} onChange={setParty} filter={(l) => l.group_name === group} />
        </label>
        <label className="field">
          <span>{vtype === "Receipt" ? "Into" : "From"} cash / bank</span>
          <LedgerSelect ledgers={ledgers} value={cash} onChange={setCash} filter={(l) => CASH_BANK.has(l.group_name)} />
        </label>
        <label className="field">
          <span>Amount ₹</span>
          <NumberInput value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label className="field" title={vtype === "Receipt" ? "Goes to TDS Receivable; the customer is credited with amount + TDS" : "Goes to TDS Payable"}>
          <span>{vtype === "Receipt" ? "TDS deducted by customer ₹" : "TDS deducted ₹"}</span>
          <NumberInput value={tds} onChange={(e) => setTds(e.target.value)} placeholder="0" />
        </label>
        <label className="field">
          <span>Cheque / UTR no.</span>
          <input value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
      </div>
      {bills.length ? (
        <>
          <div className="report-head">
            <h4>Against bills</h4>
            <button className="button small-button" onClick={autoAllocate} disabled={!total}>
              Allocate oldest first
            </button>
          </div>
          <table className="data-table compact">
            <thead>
              <tr>
                <th>Bill</th>
                <th>Date</th>
                <th className="num">Pending</th>
                <th className="num">Settle now</th>
              </tr>
            </thead>
            <tbody>
              {bills.map((b) => (
                <tr key={b.bill_ref}>
                  <td>{b.bill_ref}</td>
                  <td>{b.bill_date ? formatValue(b.bill_date, "date") : "—"}</td>
                  <td className="num">{formatValue(Math.abs(b.pending), "money")}</td>
                  <td className="num">
                    <NumberInput value={allocate[b.bill_ref] ?? ""} aria-label={`Settle now for ${b.bill_ref}`}
                      onChange={(e) => setAllocate((a) => ({ ...a, [b.bill_ref]: e.target.value }))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Allocated {formatValue(allocated, "money")} of {formatValue(total, "money")}
            {total - allocated > 0.004 ? `; ${formatValue(total - allocated, "money")} goes on account` : ""}.
          </p>
        </>
      ) : party ? (
        <p className="muted small">No pending bills; the amount goes on account (advance).</p>
      ) : null}
      <label className="field">
        <span>Narration</span>
        <input value={narration} onChange={(e) => setNarration(e.target.value)} />
      </label>
      {problem ? <div className="callout warning">{problem}</div> : null}
      <button className="button primary" onClick={() => void save()} disabled={saving || !party || !cash || !parseAmount(amount) || Boolean(problem)}>
        {saving ? "Saving…" : `Save ${vtype}`}
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <Saved voucher={saved} />
    </div>
  );
}

function LinesForm({ company, ledgers, onSaved }: Props) {
  const [vtype, setVtype] = useState<VoucherType>("Journal");
  const [date, setDate] = useState(today());
  const [narration, setNarration] = useState("");
  const [reference, setReference] = useState("");
  const [lines, setLines] = useState([{ ledger: "", dr: "", cr: "" }, { ledger: "", dr: "", cr: "" }]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<VoucherDetail | null>(null);
  const totals = useMemo(
    () => lines.reduce((t, l) => ({ dr: t.dr + parseAmount(l.dr), cr: t.cr + parseAmount(l.cr) }), { dr: 0, cr: 0 }),
    [lines],
  );
  const diff = Math.round((totals.dr - totals.cr) * 100) / 100;
  const filter = vtype === "Contra" ? (l: Ledger) => CASH_BANK.has(l.group_name) : undefined;
  const [saving, guard] = useSaving();
  const problem = badNumber(lines.flatMap((l, n): [string, string][] => [[`Debit on line ${n + 1}`, l.dr], [`Credit on line ${n + 1}`, l.cr]]));

  function changeType(next: VoucherType) {
    // A contra uses only cash and bank ledgers: drop others, which its list would hide but still post.
    if (next === "Contra") {
      const cashBank = new Set(ledgers.filter((l) => CASH_BANK.has(l.group_name)).map((l) => String(l.id)));
      setLines((all) => all.map((x) => (x.ledger && !cashBank.has(x.ledger) ? { ...x, ledger: "" } : x)));
    }
    setVtype(next);
  }

  const save = () => guard(async () => {
    setError(null);
    try {
      const voucher = await api.createVoucher(company.id, {
        vtype, date, narration, reference,
        lines: lines.filter((l) => l.ledger && (l.dr || l.cr)).map((l) => ({ ledger_id: Number(l.ledger), dr: l.dr || null, cr: l.cr || null })),
      });
      setSaved(voucher);
      setLines([{ ledger: "", dr: "", cr: "" }, { ledger: "", dr: "", cr: "" }]);
      setNarration("");
      onSaved(voucher);
    } catch (e) {
      setError((e as Error).message);
    }
  });

  return (
    <div className="entry-grid">
      <div className="report-params">
        <label className="field">
          <span>Type</span>
          <select value={vtype} onChange={(e) => changeType(e.target.value as VoucherType)}>
            {["Journal", "Contra", "Payment", "Receipt", "Sales", "Purchase", "Credit Note", "Debit Note"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Date</span>
          <input type="date" value={date} min={company.fy_start} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field">
          <span>Reference</span>
          <input value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
      </div>
      <table className="data-table compact">
        <thead>
          <tr>
            <th>Ledger</th>
            <th className="num">Debit ₹</th>
            <th className="num">Credit ₹</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {lines.map((line, i) => (
            <tr key={i}>
              <td>
                <LedgerSelect ledgers={ledgers} value={line.ledger} filter={filter}
                  onChange={(v) => setLines((all) => all.map((x, j) => (j === i ? { ...x, ledger: v } : x)))} />
              </td>
              <td className="num">
                <NumberInput value={line.dr} disabled={Boolean(line.cr)} aria-label={`Debit on line ${i + 1}`}
                  onChange={(e) => setLines((all) => all.map((x, j) => (j === i ? { ...x, dr: e.target.value } : x)))} />
              </td>
              <td className="num">
                <NumberInput value={line.cr} disabled={Boolean(line.dr)} aria-label={`Credit on line ${i + 1}`}
                  onChange={(e) => setLines((all) => all.map((x, j) => (j === i ? { ...x, cr: e.target.value } : x)))} />
              </td>
              <td>
                {lines.length > 2 ? (
                  <button className="icon-button" onClick={() => setLines((all) => all.filter((_, j) => j !== i))} aria-label="Remove line">
                    ×
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="row-total">
            <td>Total</td>
            <td className="num">{formatValue(totals.dr, "money")}</td>
            <td className="num">{formatValue(totals.cr, "money")}</td>
            <td />
          </tr>
        </tfoot>
      </table>
      <div className="sql-actions">
        <button className="button small-button" onClick={() => setLines((all) => [...all, { ledger: "", dr: "", cr: "" }])}>
          + Add line
        </button>
        {totals.dr || totals.cr ? (
          <span className={diff === 0 ? "verify verified" : "verify unverified"}>
            {diff === 0 ? "✓ Debits equal credits" : `Difference ${formatValue(Math.abs(diff), "money")} (${diff > 0 ? "more debit" : "more credit"})`}
          </span>
        ) : null}
      </div>
      <label className="field">
        <span>Narration</span>
        <input value={narration} onChange={(e) => setNarration(e.target.value)} />
      </label>
      <p className="muted small">
        Party lines (customers, suppliers) are tracked bill-wise automatically: invoices open a bill, receipts and payments go on account.
        {ledgers.some((l) => PARTIES.has(l.group_name)) ? "" : " Create customers and suppliers under Ledgers first."}
      </p>
      {problem ? <div className="callout warning">{problem}</div> : null}
      <button className="button primary" onClick={() => void save()} disabled={saving || diff !== 0 || totals.dr === 0 || Boolean(problem)}>
        {saving ? "Saving…" : `Save ${vtype}`}
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <Saved voucher={saved} />
    </div>
  );
}
