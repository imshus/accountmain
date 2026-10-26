import { todayISO } from "../../books";
import type { EntryKind } from "../../router";
import type { Metal } from "../../types";

/** What the Sale / Purchase screen holds, as typed. Numbers stay text so "12.5" or "1,250" reads as the backend reads it. */
export type EntryForm = {
  date: string; // YYYY-MM-DD
  invoiceNo: string; // "" = numbered by the books
  party: string; // customer (sale) / supplier (purchase), by name: a name not yet in the books becomes a ledger on Save
  agent: string; // salesman (sale) / purchaser (purchase)
  item: string;
  metal: Metal;
  settle: "Wt" | "Rs";
  gross: string;
  diamondCt: string;
  stoneCt: string;
  /** null = worked out from gross − (diamond + stone ct) × 0.2 g; text once typed over. */
  net: string | null;
  purity: string; // tunch %
  diamondRate: string; // ₹ per carat
  stoneRate: string; // ₹ per carat
  labourRate: string; // ₹ per gram of net weight
  metalRate: string; // ₹ per gram fine, for "in rupees"
  gst: string; // %
};

export type FieldKey =
  | "date"
  | "invoiceNo"
  | "party"
  | "agent"
  | "item"
  | "gross"
  | "net"
  | "purity"
  | "diamondCt"
  | "diamondRate"
  | "stoneCt"
  | "stoneRate"
  | "labourRate"
  | "metalRate"
  | "gst";

export type FieldErrors = Partial<Record<FieldKey, string>>;

/** Top-to-bottom order of the fields, so a failed save focuses the first one with a problem. */
export const FIELD_ORDER: FieldKey[] = [
  "date", "invoiceNo", "party", "agent", "item", "gross", "net", "purity", "metalRate", "diamondCt", "diamondRate",
  "stoneCt", "stoneRate", "labourRate", "gst",
];

export const GST_DEFAULT = "3";
export const PURITY_DEFAULT = "91.6";
/** Offered in the Item list until the shop adds its own. */
export const DEFAULT_ITEMS = ["Bangle", "Chain", "Ring", "Necklace", "Earrings", "Pendant"];

export function emptyForm(): EntryForm {
  return {
    date: todayISO(), invoiceNo: "", party: "", agent: "", item: "", metal: "gold", settle: "Wt", gross: "", diamondCt: "",
    stoneCt: "", net: null, purity: PURITY_DEFAULT, diamondRate: "", stoneRate: "", labourRate: "", metalRate: "", gst: GST_DEFAULT,
  };
}

/** After a save: a fresh bill for the next customer, keeping the choices that usually repeat. */
export function nextForm(prev: EntryForm): EntryForm {
  return { ...emptyForm(), date: prev.date, agent: prev.agent, metal: prev.metal, settle: prev.settle, purity: prev.purity,
    labourRate: prev.labourRate, metalRate: prev.metalRate, gst: prev.gst };
}

// An unsaved bill survives an accidental Back (or the Android back button) for a while.
const DRAFT_KEY = "accountsai.entry.draft";
const DRAFT_HOURS = 12;

type Draft = { companyId: number; kind: EntryKind; at: number; form: EntryForm };

export function loadDraft(companyId: number): { kind: EntryKind; form: EntryForm } | null {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "null") as Draft | null;
    if (!draft || draft.companyId !== companyId || Date.now() - draft.at > DRAFT_HOURS * 3600_000) return null;
    // A bill date carried over from an earlier day would be easy to miss: the date restarts at today.
    const sameDay = new Date(draft.at).toDateString() === new Date().toDateString();
    return { kind: draft.kind, form: { ...emptyForm(), ...draft.form, ...(sameDay ? {} : { date: todayISO() }) } };
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

/** Nothing typed that would be a pity to lose. */
function isBlank(form: EntryForm): boolean {
  return !form.invoiceNo && !form.party && !form.item && !form.gross && form.net === null && !form.diamondCt &&
    !form.stoneCt && !form.diamondRate && !form.stoneRate && !form.labourRate;
}
