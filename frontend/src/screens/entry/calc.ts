import { purityCode } from "../../books";
import { fineOf, halfUp, readAmount, toUnits, unreadable } from "../../components/accounts/shared";
import type { EntryKind } from "../../router";
import type { Company, Ledger, VoucherRow } from "../../types";
import type { EntryForm, FieldErrors, FieldKey } from "./form";

/**
 * The bill as the backend will post it, in whole mg / 0.001 ct / 0.01 % / paise with its half-up steps
 * (metal.item_weights, metal.jewellery_invoice, service.gst_invoice_lines), so the preview is the saved bill.
 */
export type Preview = {
  grossMg: number;
  carats: number; // diamond + stone, thousandths of a carat
  autoNetMg: number; // gross − (diamond + stone ct) × 0.2 g
  netMg: number;
  tunchBp: number;
  fineMg: number;
  labour: number; // paise
  diamond: number;
  stone: number;
  metalValue: number; // fine × metal rate, only when settled in rupees
  taxable: number;
  tax: number;
  cgst: number;
  sgst: number;
  igst: number;
  interState: boolean;
  roundOff: number;
  total: number;
};

const num = (text: string) => {
  const value = readAmount(text);
  return Number.isFinite(value) ? value : 0;
};
const mg = (text: string) => toUnits(num(text), 3);
const mct = (text: string) => toUnits(num(text), 3);
const paise = (text: string) => toUnits(num(text), 2);
const bp = (text: string) => toUnits(num(text), 2);

const GSTIN_STATE = /^(\d{2})[0-9A-Z]{13}$/;

/** Place of supply as the backend reads it: the GSTIN's state, else the state chosen on the ledger. */
function stateOf(party: Ledger | undefined): string | null {
  const gstin = party?.gstin?.trim().toUpperCase() ?? "";
  const hit = GSTIN_STATE.exec(gstin);
  return hit ? hit[1] : party?.state_code || null;
}

export function preview(form: EntryForm, company: Company, party: Ledger | undefined): Preview {
  const grossMg = mg(form.gross);
  const carats = mct(form.diamondCt) + mct(form.stoneCt);
  const autoNetMg = grossMg ? grossMg - halfUp(carats * 2, 10) : 0;
  const netMg = form.net !== null && form.net.trim() ? mg(form.net) : autoNetMg;
  const tunchBp = bp(form.purity);
  const fineMg = fineOf(netMg, tunchBp);
  const labour = halfUp((netMg || 0) * paise(form.labourRate), 1000);
  const diamond = halfUp(mct(form.diamondCt) * paise(form.diamondRate), 1000);
  const stone = halfUp(mct(form.stoneCt) * paise(form.stoneRate), 1000);
  const metalValue = form.settle === "Rs" ? halfUp(fineMg * paise(form.metalRate), 1000) : 0;
  const taxable = metalValue + diamond + stone + labour;
  const tax = taxable > 0 ? halfUp(taxable * bp(form.gst), 10000) : 0;
  const pos = stateOf(party);
  const interState = Boolean(pos && company.state_code && pos !== company.state_code);
  const cgst = interState ? 0 : Math.floor(tax / 2);
  const sgst = interState ? 0 : tax - cgst; // the odd paisa goes to SGST, as the books do
  const igst = interState ? tax : 0;
  const gross = taxable + tax;
  const total = taxable > 0 ? halfUp(gross, 100) * 100 : 0;
  return { grossMg, carats, autoNetMg, netMg, tunchBp, fineMg, labour, diamond, stone, metalValue, taxable, tax, cgst, sgst, igst,
    interState, roundOff: total - gross, total };
}

const NUMBER_FIELDS: [FieldKey, (f: EntryForm) => string | null][] = [
  ["gross", (f) => f.gross],
  ["net", (f) => f.net],
  ["purity", (f) => f.purity],
  ["diamondCt", (f) => f.diamondCt],
  ["diamondRate", (f) => f.diamondRate],
  ["stoneCt", (f) => f.stoneCt],
  ["stoneRate", (f) => f.stoneRate],
  ["labourRate", (f) => f.labourRate],
  ["metalRate", (f) => f.metalRate],
  ["gst", (f) => f.gst],
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
  for (const [key, get] of NUMBER_FIELDS) {
    const text = get(form);
    if (unreadable(text)) typing[key] = `"${text}" is not a number.`;
    else if (text && readAmount(text) < 0) typing[key] = "Cannot be negative.";
  }
  const all: FieldErrors = { ...typing };
  const set = (key: FieldKey, message: string) => {
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
  if (!form.item.trim()) set("item", "Choose the item.");
  if (form.net === null && p.grossMg > 0 && p.autoNetMg <= 0) set("net", "Diamonds and stones weigh more than the gross weight.");
  if (p.netMg <= 0) set(p.grossMg || form.net !== null ? "net" : "gross", "Enter the weight.");
  if (p.tunchBp <= 0 || p.tunchBp > 10000) set("purity", "Purity must be more than 0 and at most 100%.");
  if (p.netMg > 0 && p.tunchBp > 0 && p.fineMg <= 0) set("net", "The fine weight works out to 0 g.");
  if (form.settle === "Rs" && toUnits(num(form.metalRate), 2) <= 0) set("metalRate", "Give the rate per gram of fine metal.");
  if (num(form.gst) > 100) set("gst", "GST is at most 100%.");
  return { typing, all };
}

const text = (value: number) => String(value);
const rupees = (p: number) => (p ? (p / 100).toFixed(2) : null);

/** The body for POST /companies/{id}/vouchers/jewellery. Amounts we worked out go as exact rupees. */
export function payload(form: EntryForm, p: Preview, kind: EntryKind, partyId: number) {
  const sale = kind === "sale";
  const tunch = num(form.purity);
  const agent = form.agent.trim();
  return {
    vtype: sale ? "Sales" : "Purchase",
    date: form.date,
    number: form.invoiceNo.trim() || null,
    party_id: partyId,
    metal: form.metal,
    gst_rate: num(form.gst),
    metal_rate: form.settle === "Rs" ? text(num(form.metalRate)) : null,
    round_off: true,
    narration: agent ? `${sale ? "Salesman" : "Purchaser"}: ${agent}` : "",
    items: [
      {
        item: form.item.trim() || null,
        purity: form.metal === "gold" ? purityCode(tunch) : `${tunch}`,
        tunch,
        gross: p.grossMg ? text(num(form.gross)) : null,
        diamond_ct: num(form.diamondCt) ? text(num(form.diamondCt)) : null,
        stone_ct: num(form.stoneCt) ? text(num(form.stoneCt)) : null,
        net: form.net !== null && form.net.trim() ? text(num(form.net)) : null,
        diamond_value: rupees(p.diamond),
        stone_value: rupees(p.stone),
        labour_rate: num(form.labourRate) ? text(num(form.labourRate)) : null,
        settle: form.settle,
      },
    ],
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
