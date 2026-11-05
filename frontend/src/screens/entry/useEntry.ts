import { useEffect, useId, useMemo, useState } from "react";
import { api } from "../../api";
import { useBooks } from "../../books";
import { useSaving } from "../../components/accounts/shared";
import type { EntryKind } from "../../router";
import { useCompany } from "../../session";
import type { Ledger } from "../../types";
import { check, nextNumber, payload, preview } from "./calc";
import { fieldOf, isHeadKey } from "./errors";
import {
  clearDraft, emptyForm, emptyItem, fieldOrder, itemKey, loadDraft, nextForm, saveDraft, type EntryForm, type EntryItem, type FieldErrors,
  type FieldKey,
} from "./form";
import type { SavedBill } from "./SavedSheet";

export const PARTY_GROUP: Record<EntryKind, string> = { sale: "Sundry Debtors", purchase: "Sundry Creditors" };

export const sameName = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

function initialForm(companyId: number, kind: EntryKind): EntryForm {
  const draft = loadDraft(companyId);
  if (!draft) return emptyForm();
  // The customer and supplier lists differ between Sale and Purchase.
  return draft.kind === kind ? draft.form : { ...draft.form, party: "" };
}

/** State, live figures and saving of the Sale / Purchase screen: one bill of one or more items. */
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

  // Switching Sale <-> Purchase keeps the items and clears who the bill is with.
  if (formKind !== kind) {
    setFormKind(kind);
    setForm((f) => ({ ...f, party: "" }));
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
  // The design's Save stays muted until the bill has its customer / supplier and every item its name.
  const ready = Boolean(form.party.trim()) && form.items.every((item) => item.name.trim());

  const idOf = (key: FieldKey) => `${base}${key.replace(":", "-")}`;

  const focusField = (key: FieldKey) => {
    const node = document.getElementById(idOf(key));
    const target = node instanceof HTMLInputElement || node instanceof HTMLButtonElement || node instanceof HTMLSelectElement
      ? node
      : node?.querySelector<HTMLElement>("input, button, select");
    target?.focus({ preventScroll: true });
    (node ?? target)?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  /** Change the bill's own fields. A server message was about the old values, so it goes. */
  const set = (patch: Partial<Omit<EntryForm, "items">>) => {
    setForm((f) => ({ ...f, ...patch }));
    setServerErrors({});
    setGeneral(null);
  };

  /** Change one item's fields. */
  const setItem = (id: string, patch: Partial<EntryItem>) => {
    setForm((f) => ({ ...f, items: f.items.map((item) => (item.id === id ? { ...item, ...patch } : item)) }));
    setServerErrors({});
    setGeneral(null);
  };

  /** "Add more item": a new item under the others, with the last one's purity, karat and labour (they usually repeat). */
  const addItem = (): string => {
    const last = form.items[form.items.length - 1];
    const item = { ...emptyItem(), purity: last?.purity ?? "", karat: last?.karat ?? "", labourRate: last?.labourRate ?? "",
      labourBasis: last?.labourBasis ?? "" };
    setForm((f) => ({ ...f, items: [...f.items, item] }));
    return item.id;
  };

  const removeItem = (id: string) => setForm((f) => (f.items.length > 1 ? { ...f, items: f.items.filter((item) => item.id !== id) } : f));

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
      const first = fieldOrder(form).find((key) => problems.all[key]);
      if (first) {
        focusField(first);
        return;
      }
      const bill = form;
      const shown = { total: figures.total, fineMg: figures.fineMg };
      try {
        const party = await ensureParty(bill.party);
        const voucher = await api.createJewellery(company.id, payload(bill, figures, kind, party.id));
        for (const item of bill.items) if (item.name.trim()) books.addMaster("item", item.name);
        clearDraft();
        setSaved({ voucher, party: party.name, metal: bill.metal, settle: bill.settle, shown });
        setForm(nextForm(bill));
        setTried(false);
        void books.refresh();
      } catch (e) {
        const message = (e as Error).message;
        const field = fieldOf(message);
        // An item's message does not say which item: it goes under the field of a bill's only item, else at the bottom.
        const key = field && (isHeadKey(field) ? field : bill.items.length === 1 ? itemKey(bill.items[0], field) : null);
        if (key) {
          setServerErrors({ [key]: message });
          focusField(key);
        } else setGeneral(message);
      }
    });

  return {
    company, books, form, set, setItem, addItem, removeItem, figures, errors, general, saving, save, saved, setSaved, idOf,
    autoNumber, addParty, partyLedger, ready,
  };
}
