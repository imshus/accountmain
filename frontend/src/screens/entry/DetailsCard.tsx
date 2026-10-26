import type { EntryKind } from "../../router";
import type { Ledger, Metal } from "../../types";
import { Card, DatePill, Field, Input, Overline } from "../../ui";
import type { AddRequest } from "./AddNameSheet";
import { firstOpenDate } from "./calc";
import { DEFAULT_ITEMS } from "./form";
import { money, grams } from "./money";
import { Picker, type PickerOption } from "./Picker";
import { sameName, type useEntry } from "./useEntry";

type Props = { entry: ReturnType<typeof useEntry>; kind: EntryKind; ask: (request: AddRequest) => void };

/** Names in a list, plus the chosen one if it is not there (a draft, or just added), without repeats. */
function namesWith(names: string[], current: string, extra: string[] = []): PickerOption[] {
  const all: string[] = [];
  for (const name of [...names, ...extra, current]) {
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

/** Date, invoice number and who the bill is with, as on the design's first card. */
export function DetailsCard({ entry, kind, ask }: Props) {
  const { form, set, errors, idOf, books, company, autoNumber, partyLedger, figures, addParty } = entry;
  const sale = kind === "sale";
  const partyKind = sale ? "customer" : "supplier";
  const agentKind = sale ? "salesman" : "purchaser";
  const parties = namesWith(books.masters[partyKind], form.party).sort((a, b) => a.label.localeCompare(b.label));
  const agents = namesWith(books.masters[agentKind], form.agent);
  const items = namesWith(books.masters.item, form.item, DEFAULT_ITEMS);
  const partyHint = !form.party
    ? undefined
    : partyLedger
      ? `${balanceOf(partyLedger, form.metal)}${figures.interState ? " · other state: IGST" : ""}`
      : "New: added to the books when you save";

  return (
    <Card>
      <div className="entry-date" id={idOf("date")}>
        <Overline>Date</Overline>
        <DatePill value={form.date} onChange={(date) => set({ date })} min={firstOpenDate(company)} label="Bill date" />
      </div>
      {errors.date ? (
        <p className="entry-err" role="alert">
          {errors.date}
        </p>
      ) : null}

      <Field label="Invoice no" htmlFor={idOf("invoiceNo")} error={errors.invoiceNo}>
        <Input
          id={idOf("invoiceNo")}
          value={form.invoiceNo}
          onChange={(event) => set({ invoiceNo: event.target.value })}
          placeholder={autoNumber ? `Auto (${autoNumber})` : "Auto (e.g. INV-001)"}
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          maxLength={40}
          enterKeyHint="next"
          aria-invalid={Boolean(errors.invoiceNo) || undefined}
        />
      </Field>

      <Field label={sale ? "Customer name" : "Supplier name"} htmlFor={idOf("party")} error={errors.party} hint={partyHint}>
        <Picker
          id={idOf("party")}
          value={form.party}
          options={parties}
          onSelect={(party) => set({ party })}
          placeholder={sale ? "Choose customer" : "Choose supplier"}
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

      <Field label={sale ? "Sales man" : "Purchaser"} htmlFor={idOf("agent")} error={errors.agent}>
        <Picker
          id={idOf("agent")}
          value={form.agent}
          options={form.agent ? [...agents, { value: "", label: "None" }] : agents}
          onSelect={(agent) => set({ agent })}
          placeholder="Optional"
          onAdd={(typed) =>
            ask({
              title: sale ? "New sales man" : "New purchaser",
              label: "Name",
              initial: typed,
              description: "Kept on this device for quick entry.",
              submit: (name) => {
                books.addMaster(agentKind, name);
                set({ agent: name });
              },
            })
          }
        />
      </Field>

      <Field label="Item" htmlFor={idOf("item")} error={errors.item}>
        <Picker
          id={idOf("item")}
          value={form.item}
          options={items}
          onSelect={(item) => set({ item })}
          placeholder="Choose item"
          invalid={Boolean(errors.item)}
          onAdd={(typed) =>
            ask({
              title: "New item",
              label: "Item name",
              initial: typed,
              description: "Kept on this device for quick entry.",
              submit: (name) => {
                books.addMaster("item", name);
                set({ item: name });
              },
            })
          }
        />
      </Field>
    </Card>
  );
}
