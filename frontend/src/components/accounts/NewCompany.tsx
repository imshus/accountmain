import { useId, useState } from "react";
import { api } from "../../api";
import type { Company } from "../../types";
import { Button, Field, Input, Notice } from "../../ui";

type Props = {
  onCreated: (company: Company) => void;
  onCancel?: () => void;
  /** Inside a sheet (the menu's "+"): no heading or card around the form. */
  compact?: boolean;
};

/** 1 April of the financial year that today falls in. */
function currentFyStart(): string {
  const now = new Date();
  const year = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-04-01`;
}

export default function NewCompany({ onCreated, onCancel, compact = false }: Props) {
  const [name, setName] = useState("");
  const [gstin, setGstin] = useState("");
  const [fyStart, setFyStart] = useState(currentFyStart());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  const gstinId = useId();
  const fyId = useId();

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

  const form = (
    <form className="new-company__form" onSubmit={(e) => void save(e)}>
      <Field label="Company name" htmlFor={nameId}>
        <Input id={nameId} value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} placeholder="Gupta Jewellers" data-autofocus />
      </Field>
      <Field label="GSTIN (optional)" htmlFor={gstinId} hint="Sets your state, so bills split into CGST + SGST or IGST correctly.">
        <Input
          id={gstinId}
          value={gstin}
          onChange={(e) => setGstin(e.target.value.toUpperCase())}
          maxLength={15}
          placeholder="27ABCDE1234F1Z5"
          autoCapitalize="characters"
          autoCorrect="off"
          spellCheck={false}
        />
      </Field>
      <Field
        label="Books begin from (FY start)"
        htmlFor={fyId}
        hint="Opening balances are as on this day and no entry can be dated earlier. To import last year's registers, choose 1 April of that year. It can be changed (under Ledgers) until the first entry."
      >
        <Input id={fyId} type="date" value={fyStart} onChange={(e) => setFyStart(e.target.value)} required />
      </Field>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div className="new-company__actions">
        {onCancel ? <Button onClick={onCancel}>Cancel</Button> : null}
        <Button type="submit" variant="brand" busy={saving} disabled={!name.trim()}>
          {saving ? "Creating…" : "Create company"}
        </Button>
      </div>
    </form>
  );

  if (compact) return form;
  return (
    <section className="panel narrow-panel new-company">
      <h2>New company books</h2>
      <p className="muted small">
        Double-entry books, the way Tally keeps them: every voucher debits and credits ledgers by the same amount, so the trial
        balance and balance sheet always tally. The 28 standard groups and the usual ledgers (Cash, Capital, Sales, Purchase,
        CGST/SGST/IGST input and output, TDS payable, Round off) are created for you.
      </p>
      {form}
    </section>
  );
}
