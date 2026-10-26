import { useEffect, useId, useMemo, useState } from "react";
import { api } from "../../api";
import { useBooks } from "../../books";
import { useSaving } from "../../components/accounts/shared";
import type { EntryKind } from "../../router";
import { useCompany } from "../../session";
import type { Ledger } from "../../types";
import { check, nextNumber, payload, preview } from "./calc";
import { fieldOf } from "./errors";
import { FIELD_ORDER, clearDraft, emptyForm, loadDraft, nextForm, saveDraft, type EntryForm, type FieldErrors, type FieldKey } from "./form";
import type { SavedBill } from "./SavedSheet";

export const PARTY_GROUP: Record<EntryKind, string> = { sale: "Sundry Debtors", purchase: "Sundry Creditors" };

export const sameName = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

function initialForm(companyId: number, kind: EntryKind): EntryForm {
  const draft = loadDraft(companyId);
  if (!draft) return emptyForm();
  // The party and salesman lists differ between Sale and Purchase.
  return draft.kind === kind ? draft.form : { ...draft.form, party: "", agent: "" };
}

/** State, live figures and saving of the Sale / Purchase screen. */
export function useEntry(kind: EntryKind) {
  const company = useCompany();
  const books = useBooks();
  const base = useId();
  const [form, setForm] = useState(() => initialForm(company.id, kind));
  const [formKind, setFormKind] = useState(kind);
  const [tried, setTried] = useState(false);
  const [serverErrors, setServerErrors] = useState<FieldErrors>({});
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedBill | null>(null);
  const [saving, guard] = useSaving();

  // Switching Sale <-> Purchase keeps the weights and clears who the bill is with.
  if (formKind !== kind) {
    setFormKind(kind);
    setForm((f) => ({ ...f, party: "", agent: "" }));
    setTried(false);
    setServerErrors({});
    setGeneral(null);
  }

  useEffect(() => saveDraft(company.id, kind, form), [company.id, kind, form]);

  const partyLedger: Ledger | undefined = books.ledgers.find((l) => sameName(l.name, form.party));
  const figures = useMemo(() => preview(form, company, partyLedger), [form, company, partyLedger]);
  const problems = useMemo(() => check(form, figures, kind, company), [form, figures, kind, company]);
  const errors: FieldErrors = { ...(tried ? problems.all : problems.typing), ...serverErrors };
  const autoNumber = nextNumber(books.vouchers, books.vouchers.length >= books.voucherTotal, kind, form.date);

  const idOf = (key: FieldKey) => `${base}${key}`;

  const focusField = (key: FieldKey) => {
    const node = document.getElementById(idOf(key));
    const target = node instanceof HTMLInputElement || node instanceof HTMLButtonElement || node instanceof HTMLSelectElement
      ? node
      : node?.querySelector<HTMLElement>("input, button, select");
    target?.focus({ preventScroll: true });
    (node ?? target)?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  /** Change some fields. A server message was about the old values, so it goes. */
  const set = (patch: Partial<EntryForm>) => {
    setForm((f) => ({ ...f, ...patch }));
    setServerErrors({});
    setGeneral(null);
  };

  const ensureParty = async (name: string): Promise<Ledger> => {
    const known = books.ledgers.find((l) => sameName(l.name, name));
    if (known) return known;
    // A walk-in party is local: the company's state makes it CGST + SGST, as the books would otherwise assume.
    const made = await api.saveLedger(company.id, null, { name: name.trim(), group: PARTY_GROUP[kind], opening: "0", state_code: company.state_code });
    // Known from now on, even if the bill itself is then refused (a retry must not make the ledger twice).
    void books.refresh();
    return made;
  };

  /** "Add new" customer / supplier: a ledger in the right group, made now so its GSTIN sets the tax. */
  const addParty = async (name: string, gstin: string) => {
    const known = books.ledgers.find((l) => sameName(l.name, name));
    if (!known) {
      await api.saveLedger(company.id, null, {
        name, group: PARTY_GROUP[kind], opening: "0", gstin: gstin || undefined, state_code: gstin ? undefined : company.state_code,
      });
      await books.refresh();
    }
    set({ party: known?.name ?? name });
  };

  const save = () =>
    guard(async () => {
      setTried(true);
      setGeneral(null);
      const first = FIELD_ORDER.find((key) => problems.all[key]);
      if (first) {
        focusField(first);
        return;
      }
      const bill = form;
      const shown = { total: figures.total, fineMg: figures.fineMg };
      try {
        const party = await ensureParty(bill.party);
        const voucher = await api.createJewellery(company.id, payload(bill, figures, kind, party.id));
        if (bill.item.trim()) books.addMaster("item", bill.item);
        if (bill.agent.trim()) books.addMaster(kind === "sale" ? "salesman" : "purchaser", bill.agent);
        clearDraft();
        setSaved({ voucher, party: party.name, metal: bill.metal, settle: bill.settle, shown });
        setForm(nextForm(bill));
        setTried(false);
        void books.refresh();
      } catch (e) {
        const message = (e as Error).message;
        const field = fieldOf(message);
        if (field) {
          setServerErrors({ [field]: message });
          focusField(field);
        } else setGeneral(message);
      }
    });

  return { company, books, form, set, figures, errors, general, saving, save, saved, setSaved, idOf, autoNumber, addParty, partyLedger };
}
