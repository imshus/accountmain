import { useState } from "react";
import { api } from "../../api";
import type { Company } from "../../types";

type Props = {
  onCreated: (company: Company) => void;
  onCancel?: () => void;
};

/** 1 April of the financial year that today falls in. */
function currentFyStart(): string {
  const now = new Date();
  const year = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-04-01`;
}

export default function NewCompany({ onCreated, onCancel }: Props) {
  const [name, setName] = useState("");
  const [gstin, setGstin] = useState("");
  const [fyStart, setFyStart] = useState(currentFyStart());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      onCreated(await api.createCompany({ name: name.trim(), gstin: gstin.trim() || undefined, fy_start: fyStart }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel narrow-panel">
      <h1>New company books</h1>
      <p className="muted">
        Double-entry books, the way Tally keeps them: every voucher debits and credits ledgers by the same amount, so the trial
        balance and balance sheet always tally. The 28 standard groups and the usual ledgers (Cash, Capital, Sales, Purchase,
        CGST/SGST/IGST input and output, TDS payable, Round off) are created for you.
      </p>
      <form className="stack-form" onSubmit={(e) => void save(e)}>
        <label className="field">
          <span>Company name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} autoFocus />
        </label>
        <label className="field">
          <span>GSTIN (optional; sets your state for CGST+SGST vs IGST)</span>
          <input value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} maxLength={15} placeholder="27ABCDE1234F1Z5" />
        </label>
        <label className="field">
          <span>Books begin from (financial year start)</span>
          <input type="date" value={fyStart} onChange={(e) => setFyStart(e.target.value)} required />
        </label>
        <p className="muted small">
          Opening balances are as on this day and no voucher can be dated earlier, so to import last year's registers choose 1 April
          of that year. It can be changed later (under Ledgers) only until the first voucher is entered.
        </p>
        {error ? <div className="callout warning">{error}</div> : null}
        <div className="sql-actions">
          <button className="button primary" type="submit" disabled={saving || !name.trim()}>
            {saving ? "Creating…" : "Create company"}
          </button>
          {onCancel ? (
            <button className="button" type="button" onClick={onCancel}>
              Cancel
            </button>
          ) : null}
        </div>
      </form>
    </section>
  );
}
