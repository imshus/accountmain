import type { EntryKind } from "../../router";
import type { Ledger, Metal } from "../../types";
import { Card, DatePill, Field, Overline } from "../../ui";
import type { AddRequest } from "./AddNameSheet";
import { firstOpenDate } from "./calc";
import { money, grams } from "./money";
import { Picker, type PickerOption } from "./Picker";
import { sameName, type useEntry } from "./useEntry";

type Props = { entry: ReturnType<typeof useEntry>; kind: EntryKind; ask: (request: AddRequest) => void };

/** Names in a list, plus the chosen one if it is not there (a draft, or just added), without repeats. */
function namesWith(names: string[], current: string): PickerOption[] {
  const all: string[] = [];
  for (const name of [...names, current]) {
    if (name.trim() && !all.some((n) => sameName(n, name))) all.push(name.trim());
  }
  return all.map((name) => ({ value: name, label: name }));
}

/** "₹5,923 to receive · 9.480 g gold to receive", from the party's ledger (+ = Dr: owes us). */
function balanceOf(ledger: Ledger, metal: Metal): string {
  const parts: string[] = [];
  const rs = ledger.closing_paise;
  if (rs) parts.push(`${money(Math.abs(rs))} ${rs > 0 ? "to receive" : "to pay"}`);
  const mg = ledger.metal?.[metal]?.closing_mg ?? 0;
  if (mg) parts.push(`${grams(Math.abs(mg))} ${metal} ${mg > 0 ? "to receive" : "to pay"}`);
  return parts.length ? `Balance: ${parts.join(" · ")}` : "No balance yet";
}

/** The design's first card: the date and invoice chips, and who the bill is with. */
export function HeaderCard({ entry, kind, ask }: Props) {
  const { form, set, errors, idOf, books, company, autoNumber, partyLedger, figures, addParty } = entry;
  const sale = kind === "sale";
  const parties = namesWith(books.masters[sale ? "customer" : "supplier"], form.party).sort((a, b) => a.label.localeCompare(b.label));
  const partyHint = !form.party
    ? undefined
    : partyLedger
      ? `${balanceOf(partyLedger, form.metal)}${figures.interState ? " · other state: IGST" : ""}`
      : "New: added to the books when you save";
  const shownNumber = form.invoiceNo || autoNumber || "Auto";

  return (
    <Card>
      <div className="entry-chiprow" id={idOf("date")}>
        <Overline>Date</Overline>
        <DatePill value={form.date} onChange={(date) => set({ date })} min={firstOpenDate(company)} label="Bill date" />
      </div>
      {errors.date ? (
        <p className="entry-err" role="alert">
          {errors.date}
        </p>
      ) : null}

      <div className="entry-chiprow">
        <label className="ui-overline" htmlFor={idOf("invoiceNo")}>
          Invoice
        </label>
        {/* The number the books will give, in the design's chip; typing over it keeps the bill's own number. */}
        <input
          id={idOf("invoiceNo")}
          className="entry-chip"
          value={form.invoiceNo}
          onChange={(event) => set({ invoiceNo: event.target.value })}
          placeholder={autoNumber ?? "Auto"}
          size={Math.max(6, shownNumber.length)}
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          maxLength={40}
          enterKeyHint="next"
          aria-label="Invoice number (blank: numbered by the books)"
          aria-invalid={Boolean(errors.invoiceNo) || undefined}
        />
      </div>
      {errors.invoiceNo ? (
        <p className="entry-err" role="alert">
          {errors.invoiceNo}
        </p>
      ) : null}

      <Field label={sale ? "Customer name" : "Supplier name"} htmlFor={idOf("party")} error={errors.party} hint={partyHint}>
        <Picker
          id={idOf("party")}
          value={form.party}
          options={parties}
          onSelect={(party) => set({ party })}
          placeholder="Select"
          invalid={Boolean(errors.party)}
          loading={books.loading && !books.ledgers.length}
          onAdd={(typed) =>
            ask({
              title: sale ? "New customer" : "New supplier",
              label: sale ? "Customer name" : "Supplier name",
              initial: typed,
              withGstin: true,
              description: `Added to the books under ${sale ? "Sundry Debtors" : "Sundry Creditors"}.`,
              submit: addParty,
            })
          }
        />
      </Field>
    </Card>
  );
}
