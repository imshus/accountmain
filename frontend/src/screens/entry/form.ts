import { todayISO } from "../../books";
import type { EntryKind } from "../../router";
import type { Metal } from "../../types";

/** What labour is charged on: the gross or the net weight (the design's "Per": Gr. Wt / Nt. Wt.); "" (Select, as the
 * design starts) is the net weight, as the books charge it. */
export type LabourBasis = "gross" | "net" | "";

/** One item of the bill, as typed (the design's Item, Gold, Diamond, Color Stone and Labour cards). Numbers stay text so
 * "12.5" or "1,250" reads as the backend reads it. A null value is worked out (net from gross, a value from weight ×
 * rate) until typed over. */
export type EntryItem = {
  id: string; // stable, for React and the fields' ids
  name: string;
  code: string; // jewell code (the tag no.)
  design: string;
  gross: string;
  net: string | null; // null: gross − (diamond + stone ct) × 0.2 g
  purity: string; // tunch %
  karat: string; // "" = from the purity (91.6 -> 22K)
  diaShape: string;
  diaColour: string;
  diaClarity: string;
  diaCt: string;
  diaRate: string; // ₹ per carat
  diaValue: string | null; // null: carats × rate
  stnShape: string;
  stnColour: string;
  stnClarity: string;
  stnCt: string;
  stnRate: string;
  stnValue: string | null;
  labourRate: string; // ₹ per gram of the basis weight
  labourBasis: LabourBasis;
  labourValue: string | null; // null: rate × gross or net weight
};

/** The whole bill: when, its number, who with, and its items. */
export type EntryForm = {
  date: string; // YYYY-MM-DD
  invoiceNo: string; // "" = numbered by the books
  party: string; // customer (sale) / supplier (purchase), by name: a name not yet in the books becomes a ledger on Save
  items: EntryItem[];
  metal: Metal;
  settle: "Wt" | "Rs";
  metalRate: string; // ₹ per gram fine, for "in rupees"
  gst: string; // %
};

/** The bill's own fields. */
export type HeadKey = "date" | "invoiceNo" | "party";
/** An item's fields that can have a problem. */
export type ItemField = "name" | "gross" | "net" | "purity" | "diaCt" | "diaRate" | "diaValue" | "stnCt" | "stnRate" | "stnValue"
  | "labourRate" | "labourValue";
/** A field's key: a head key, or "<item id>:<field>". */
export type FieldKey = HeadKey | `${string}:${ItemField}`;

export type FieldErrors = Partial<Record<FieldKey, string>>;

export const ITEM_FIELDS: ItemField[] = ["name", "gross", "net", "purity", "diaCt", "diaRate", "diaValue", "stnCt", "stnRate",
  "stnValue", "labourRate", "labourValue"];

export const itemKey = (item: EntryItem, field: ItemField): FieldKey => `${item.id}:${field}`;

/** Top-to-bottom order of the fields, so a failed save focuses the first one with a problem. */
export function fieldOrder(form: EntryForm): FieldKey[] {
  return ["date", "invoiceNo", "party", ...form.items.flatMap((item) => ITEM_FIELDS.map((f) => itemKey(item, f)))];
}

// No GST on the form (the owner's design): the bill is the labour, diamond and stone amounts.
export const GST_DEFAULT = "0";
/** The design's karat list, and the purity each fills in when the purity is still empty. */
export const KARATS: [string, string][] = [["24K", "99.9"], ["22K", "91.6"], ["18K", "75"], ["14K", "58.5"]];
/** Offered in the Item name list until the shop adds its own. */
export const DEFAULT_ITEMS = ["Bangle", "Chain", "Ring", "Necklace", "Earrings", "Pendant"];

let made = 0;
const newId = () => `i${Date.now().toString(36)}${(made++).toString(36)}`;

export function emptyItem(): EntryItem {
  return {
    id: newId(), name: "", code: "", design: "", gross: "", net: null, purity: "", karat: "",
    diaShape: "", diaColour: "", diaClarity: "", diaCt: "", diaRate: "", diaValue: null,
    stnShape: "", stnColour: "", stnClarity: "", stnCt: "", stnRate: "", stnValue: null,
    labourRate: "", labourBasis: "", labourValue: null,
  };
}

export function emptyForm(): EntryForm {
  return { date: todayISO(), invoiceNo: "", party: "", items: [emptyItem()], metal: "gold", settle: "Wt", metalRate: "", gst: GST_DEFAULT };
}

/** After a save: a fresh bill for the next customer, keeping the choices that usually repeat (the first item's purity,
 * karat and labour). */
export function nextForm(prev: EntryForm): EntryForm {
  const first = prev.items[0];
  const item = { ...emptyItem(), purity: first?.purity ?? "", karat: first?.karat ?? "", labourRate: first?.labourRate ?? "",
    labourBasis: first?.labourBasis ?? "" };
  return { ...emptyForm(), date: prev.date, items: [item] };
}

// An unsaved bill survives an accidental Back (or the Android back button) for a while. v2: bills of several items.
const DRAFT_KEY = "accountsai.entry.draft.v2";
const DRAFT_HOURS = 12;

type Draft = { companyId: number; kind: EntryKind; at: number; form: EntryForm };

export function loadDraft(companyId: number): { kind: EntryKind; form: EntryForm } | null {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "null") as Draft | null;
    if (!draft || draft.companyId !== companyId || Date.now() - draft.at > DRAFT_HOURS * 3600_000) return null;
    if (!Array.isArray(draft.form?.items) || !draft.form.items.length) return null;
    // A bill date carried over from an earlier day would be easy to miss: the date restarts at today.
    const sameDay = new Date(draft.at).toDateString() === new Date().toDateString();
    // Fields the form does not show (metal, settlement, GST) restart at their defaults, never hidden values.
    const base = emptyForm();
    return {
      kind: draft.kind,
      form: {
        ...base, date: sameDay ? draft.form.date : base.date, invoiceNo: draft.form.invoiceNo ?? "", party: draft.form.party ?? "",
        items: draft.form.items.map((item) => ({ ...emptyItem(), ...item })),
      },
    };
  } catch {
    return null;
  }
}

export function saveDraft(companyId: number, kind: EntryKind, form: EntryForm): void {
  try {
    if (isBlank(form)) sessionStorage.removeItem(DRAFT_KEY);
    else sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ companyId, kind, at: Date.now(), form } satisfies Draft));
  } catch {
    // Storage blocked: the form simply is not kept.
  }
}

export function clearDraft(): void {
  try {
    sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    // Nothing to clear.
  }
}

const TYPED: (keyof EntryItem)[] = ["name", "code", "design", "gross", "net", "purity", "karat", "diaShape", "diaColour", "diaClarity",
  "diaCt", "diaRate", "diaValue", "stnShape", "stnColour", "stnClarity", "stnCt", "stnRate", "stnValue", "labourRate", "labourValue"];

/** Nothing typed that would be a pity to lose. */
function isBlank(form: EntryForm): boolean {
  return !form.invoiceNo && !form.party && form.items.every((item) => TYPED.every((key) => !item[key]));
}
