import { purityCode } from "../../books";
import { fineOf, halfUp, readAmount, toUnits, unreadable } from "../../components/accounts/shared";
import type { EntryKind } from "../../router";
import type { Company, Ledger, VoucherRow } from "../../types";
import { itemKey, type EntryForm, type EntryItem, type FieldErrors, type ItemField } from "./form";

/**
 * One item as the backend will post it, in whole mg / 0.001 ct / 0.01 % / paise with its half-up steps
 * (metal.item_weights, metal.jewellery_invoice), so the preview is the saved bill.
 */
export type ItemPreview = {
  grossMg: number;
  diaMct: number;
  stnMct: number;
  autoNetMg: number; // gross − (diamond + stone ct) × 0.2 g
  netMg: number;
  tunchBp: number;
  fineMg: number;
  autoDiamond: number; // paise: carats × rate
  diamond: number; // the value typed, else the worked-out one
  autoStone: number;
  stone: number;
  autoLabour: number; // rate × the basis weight
  labour: number;
};

/** The bill: its items, their sums, and the total as service.gst_invoice_lines rounds it. */
export type Preview = {
  items: ItemPreview[];
  grossMg: number;
  netMg: number;
  fineMg: number;
  diaMct: number;
  diamond: number;
  stone: number;
  labour: number;
  metalValue: number; // fine × metal rate, only when settled in rupees
  taxable: number;
  tax: number;
  interState: boolean;
  roundOff: number;
  total: number;
};

const num = (text: string | null) => {
  const value = readAmount(text ?? "");
  return Number.isFinite(value) ? value : 0;
};
const mg = (text: string | null) => toUnits(num(text), 3);
const mct = (text: string | null) => toUnits(num(text), 3);
const paise = (text: string | null) => toUnits(num(text), 2);
const bp = (text: string | null) => toUnits(num(text), 2);
const typed = (text: string | null) => text !== null && text.trim() !== "";

const GSTIN_STATE = /^(\d{2})[0-9A-Z]{13}$/;

/** Place of supply as the backend reads it: the GSTIN's state, else the state chosen on the ledger. */
function stateOf(party: Ledger | undefined): string | null {
  const gstin = party?.gstin?.trim().toUpperCase() ?? "";
  const hit = GSTIN_STATE.exec(gstin);
  return hit ? hit[1] : party?.state_code || null;
}

export function previewItem(item: EntryItem): ItemPreview {
  const grossMg = mg(item.gross);
  const diaMct = mct(item.diaCt);
  const stnMct = mct(item.stnCt);
  const autoNetMg = grossMg ? grossMg - halfUp((diaMct + stnMct) * 2, 10) : 0;
  const netMg = typed(item.net) ? mg(item.net) : autoNetMg;
  const tunchBp = bp(item.purity);
  const fineMg = fineOf(netMg, tunchBp);
  const autoDiamond = halfUp(diaMct * paise(item.diaRate), 1000);
  const autoStone = halfUp(stnMct * paise(item.stnRate), 1000);
  const basisMg = item.labourBasis === "gross" ? grossMg : netMg;
  const autoLabour = halfUp((basisMg || 0) * paise(item.labourRate), 1000);
  return {
    grossMg, diaMct, stnMct, autoNetMg, netMg, tunchBp, fineMg,
    autoDiamond, diamond: typed(item.diaValue) ? paise(item.diaValue) : autoDiamond,
    autoStone, stone: typed(item.stnValue) ? paise(item.stnValue) : autoStone,
    autoLabour, labour: typed(item.labourValue) ? paise(item.labourValue) : autoLabour,
  };
}

export function preview(form: EntryForm, company: Company, party: Ledger | undefined): Preview {
  const items = form.items.map(previewItem);
  const sum = (key: keyof ItemPreview) => items.reduce((n, p) => n + p[key], 0);
  const metalValue = form.settle === "Rs" ? halfUp(sum("fineMg") * paise(form.metalRate), 1000) : 0;
  const taxable = metalValue + sum("diamond") + sum("stone") + sum("labour");
  const tax = taxable > 0 ? halfUp(taxable * bp(form.gst), 10000) : 0;
  const pos = stateOf(party);
  const interState = Boolean(pos && company.state_code && pos !== company.state_code);
  const gross = taxable + tax;
  const total = taxable > 0 ? halfUp(gross, 100) * 100 : 0;
  return {
    items, grossMg: sum("grossMg"), netMg: sum("netMg"), fineMg: sum("fineMg"), diaMct: sum("diaMct"), diamond: sum("diamond"),
    stone: sum("stone"), labour: sum("labour"), metalValue, taxable, tax, interState, roundOff: total - gross, total,
  };
}

const NUMBER_FIELDS: [ItemField, (item: EntryItem) => string | null][] = [
  ["gross", (i) => i.gross],
  ["net", (i) => i.net],
  ["purity", (i) => i.purity],
  ["diaCt", (i) => i.diaCt],
  ["diaRate", (i) => i.diaRate],
  ["diaValue", (i) => i.diaValue],
  ["stnCt", (i) => i.stnCt],
  ["stnRate", (i) => i.stnRate],
  ["stnValue", (i) => i.stnValue],
  ["labourRate", (i) => i.labourRate],
  ["labourValue", (i) => i.labourValue],
];

const addDays = (iso: string, days: number) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** The first date the books accept: after the locked period, not before the books begin. */
export function firstOpenDate(company: Company): string {
  const start = company.fy_start.slice(0, 10);
  const afterLock = company.locked_until ? addDays(company.locked_until.slice(0, 10), 1) : "";
  return afterLock > start ? afterLock : start;
}

/**
 * Problems the backend would reject (or that make no bill). `typing` problems (unreadable numbers) show at once;
 * the rest once Save was tried.
 */
export function check(form: EntryForm, p: Preview, kind: EntryKind, company: Company): { typing: FieldErrors; all: FieldErrors } {
  const typing: FieldErrors = {};
  form.items.forEach((item) => {
    for (const [field, get] of NUMBER_FIELDS) {
      const text = get(item);
      const key = itemKey(item, field);
      if (unreadable(text)) typing[key] = `"${text}" is not a number.`;
      else if (text && readAmount(text) < 0) typing[key] = "Cannot be negative.";
    }
  });
  const all: FieldErrors = { ...typing };
  const set = (key: keyof FieldErrors, message: string) => {
    if (!all[key]) all[key] = message;
  };
  const opens = firstOpenDate(company);
  if (form.date < opens) {
    set("date", company.locked_until && opens > company.fy_start.slice(0, 10)
      ? `Books are locked up to ${company.locked_until.slice(0, 10).split("-").reverse().join("/")}; choose a later date.`
      : `The books begin on ${opens.split("-").reverse().join("/")}; choose that date or later.`);
  }
  const number = form.invoiceNo.trim();
  if (number && kind === "sale") {
    if (number.length > 16) set("invoiceNo", `At most 16 characters for a GST invoice (this has ${number.length}).`);
    else if (!/^[A-Za-z0-9/-]+$/.test(number)) set("invoiceNo", "Only letters, digits, / and - (GST Rule 46).");
  } else if (number.length > 40) set("invoiceNo", "At most 40 characters.");
  if (!form.party.trim()) set("party", kind === "sale" ? "Choose the customer." : "Choose the supplier.");
  form.items.forEach((item, i) => {
    const f = p.items[i];
    const key = (field: ItemField) => itemKey(item, field);
    if (!item.name.trim()) set(key("name"), "Enter the item name.");
    if (item.net === null && f.grossMg > 0 && f.autoNetMg <= 0) set(key("net"), "Diamonds and stones weigh more than the gross weight.");
    if (f.netMg <= 0) set(key(f.grossMg || item.net !== null ? "net" : "gross"), "Enter the weight.");
    if (f.tunchBp <= 0 || f.tunchBp > 10000) set(key("purity"), "Purity must be more than 0 and at most 100%.");
    if (f.netMg > 0 && f.tunchBp > 0 && f.fineMg <= 0) set(key("net"), "The fine weight works out to 0 g.");
  });
  return { typing, all };
}

const text = (value: number) => String(value);
const rupees = (p: number) => (p ? (p / 100).toFixed(2) : null);
const words = (value: string) => value.trim() || null;

/** The body for POST /companies/{id}/vouchers/jewellery: one line per item. Amounts we worked out go as exact rupees. */
export function payload(form: EntryForm, p: Preview, kind: EntryKind, partyId: number) {
  const sale = kind === "sale";
  return {
    vtype: sale ? "Sales" : "Purchase",
    date: form.date,
    number: form.invoiceNo.trim() || null,
    party_id: partyId,
    metal: form.metal,
    gst_rate: num(form.gst),
    metal_rate: form.settle === "Rs" ? text(num(form.metalRate)) : null,
    round_off: true,
    narration: "",
    items: form.items.map((item, i) => {
      const f = p.items[i];
      const tunch = num(item.purity);
      return {
        item: words(item.name),
        tag_no: words(item.code),
        design_no: words(item.design),
        purity: form.metal === "gold" ? item.karat || purityCode(tunch) : `${tunch}`,
        tunch,
        gross: f.grossMg ? text(num(item.gross)) : null,
        net: typed(item.net) ? text(num(item.net)) : null,
        diamond_ct: f.diaMct ? text(num(item.diaCt)) : null,
        diamond_value: rupees(f.diamond),
        diamond_shape: words(item.diaShape),
        colour: words(item.diaColour),
        clarity: words(item.diaClarity),
        stone_ct: f.stnMct ? text(num(item.stnCt)) : null,
        stone_value: rupees(f.stone),
        stone_shape: words(item.stnShape),
        stone_colour: words(item.stnColour),
        stone_clarity: words(item.stnClarity),
        // The books charge labour per gram of net weight: a typed value, or labour on the gross weight, goes as the amount.
        labour_rate: num(item.labourRate) && item.labourBasis !== "gross" && !typed(item.labourValue) ? text(num(item.labourRate)) : null,
        labour_value: typed(item.labourValue) || item.labourBasis === "gross" ? rupees(f.labour) ?? "0" : null,
        settle: form.settle,
      };
    }),
  };
}

const PREFIX = { sale: "INV", purchase: "PUR" } as const;

/** The number the books will give a blank invoice (service.next_number), when every entry is loaded; else null. */
export function nextNumber(vouchers: VoucherRow[], complete: boolean, kind: EntryKind, date: string): string | null {
  if (!complete || !/^\d{4}-\d{2}-\d{2}/.test(date)) return null;
  const year = Number(date.slice(0, 4));
  const startYear = Number(date.slice(5, 7)) >= 4 ? year : year - 1;
  const start = `${startYear}-04-01`;
  const end = `${startYear + 1}-03-31`;
  const prefix = `${PREFIX[kind]}/${String(startYear % 100).padStart(2, "0")}-${String((startYear + 1) % 100).padStart(2, "0")}/`;
  const vtype = kind === "sale" ? "Sales" : "Purchase";
  const used = vouchers
    .filter((v) => v.vtype === vtype && v.date >= start && v.date <= end && v.number.startsWith(prefix))
    .map((v) => Number(/(\d+)$/.exec(v.number)?.[1] ?? NaN))
    .filter(Number.isFinite);
  return `${prefix}${String(used.length ? Math.max(...used) + 1 : 1).padStart(4, "0")}`;
}
