import { useCallback, useRef, useState } from "react";
import type { InputHTMLAttributes } from "react";
import { formatGrams, formatValue } from "../../format";
import type { Ledger, VoucherDetail } from "../../types";

export const CASH_BANK = new Set(["Cash-in-Hand", "Bank Accounts", "Bank OD A/c"]);
export const PARTIES = new Set(["Sundry Debtors", "Sundry Creditors"]);

/** A date as YYYY-MM-DD in the device's own time zone (toISOString would give the UTC date). */
export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Today's local date: at 01:30 IST on 1 April it is 1 April, not 31 March. */
export const today = () => isoDate(new Date());

// The same readings as the backend's excel_loader.to_number, so the live totals match what is posted.
const CURRENCY = /(₹|rs\.?|inr|usd|eur|gbp|\$|€|£)/gi;
const DR_CR = /^(.*\d\)?)\s*(dr|cr)\.?$/i;
const DR_CR_PREFIX = /^(dr|cr)\.?\s*([\d(].*)$/i;
const PLAIN = /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i;

/**
 * Read an amount, weight or percent as the backend does: "1,23,456.50", "Rs 500", "5,000/-",
 * "(500)" or "500-" (minus), "1,000 Cr" (minus) / "1,000 Dr", "76%", "-" (zero).
 * Blank is 0; anything else unreadable is NaN.
 */
export function readAmount(text: string): number {
  let t = text.replace(CURRENCY, "").replace(/,/g, "").replace(/ /g, "").replace(/−/g, "-").trim();
  if (!t) return 0;
  if (t.endsWith("/-")) t = t.slice(0, -2).trim();
  let marker: string | null = null;
  const suffixed = DR_CR.exec(t);
  const prefixed = DR_CR_PREFIX.exec(t);
  if (suffixed) [t, marker] = [suffixed[1].trim(), suffixed[2].toLowerCase()];
  else if (prefixed) [t, marker] = [prefixed[2].trim(), prefixed[1].toLowerCase()];
  t = t.replace(/%+$/, "");
  let sign = 1;
  if (t.startsWith("(") && t.endsWith(")")) [sign, t] = [-1, t.slice(1, -1)];
  else if (t.length > 1 && t.endsWith("-") && /^\d+$/.test(t.slice(0, -1).replace(".", ""))) [sign, t] = [-1, t.slice(0, -1)];
  else if (t.startsWith("-") && t.length > 1) [sign, t] = [-1, t.slice(1)];
  if (marker) {
    if (sign < 0) return NaN; // "(1,000) Cr" or "-500 Dr": two signs, ambiguous
    sign = marker === "cr" ? -1 : 1;
  }
  if (t === "-" || t === "–") return 0; // accounting formats print zero as a dash
  if (!PLAIN.test(t)) return NaN;
  const value = Number(t);
  return Number.isFinite(value) ? sign * value : NaN;
}

/** An amount for live totals: unreadable text counts as 0 (Save stays disabled until it is fixed). */
export function parseAmount(text: string): number {
  const value = readAmount(text);
  return Number.isFinite(value) ? value : 0;
}

/** True when something is typed that the backend could not read as a number. */
export function unreadable(text: string | null | undefined): boolean {
  return Boolean(text?.trim()) && Number.isNaN(readAmount(text ?? ""));
}

/** The message for the first field the backend could not read, or null when every field reads as a number. */
export function badNumber(fields: [string, string | null | undefined][]): string | null {
  const bad = fields.find(([, text]) => unreadable(text));
  return bad ? `${bad[0]} "${bad[1]}" is not a number. Write it like 1,23,456.50 (Rs, /-, Dr/Cr and brackets for minus are fine).` : null;
}

/** Round half away from zero to `places` decimals, as the backend (and Excel) do. */
export function roundTo(value: number, places: number): number {
  const factor = 10 ** places;
  return (Math.sign(value) * Math.round(Math.abs(value) * factor + 1e-9)) / factor;
}

/**
 * Whole units of 10^-places, as the backend's Decimal(str(x)) rounded half up: rupees -> paise (1.005 -> 101),
 * grams -> mg, tunch % -> hundredths. It works on the decimal digits, so 1.005 is not read as 1.00499….
 */
export function toUnits(value: number, places: number): number {
  if (!Number.isFinite(value) || value === 0) return 0;
  const text = String(Math.abs(value));
  if (/e/i.test(text)) return Math.sign(value) * Math.round(Math.abs(value) * 10 ** places);
  const [whole, frac = ""] = text.split(".");
  const kept = Number(whole + frac.slice(0, places).padEnd(places, "0"));
  const up = Number(frac.charAt(places) || "0") >= 5 ? 1 : 0;
  return Math.sign(value) * (kept + up);
}

/** Integer division rounded half away from zero (the backend's half_up). */
export function halfUp(numerator: number, denominator: number): number {
  const q = Math.floor(Math.abs(numerator) / denominator);
  const n = q + (2 * (Math.abs(numerator) - q * denominator) >= denominator ? 1 : 0);
  return numerator >= 0 ? n : -n;
}

/** Grams as typed -> whole milligrams, as the backend's to_mg. */
export const toMg = (text: string) => toUnits(parseAmount(text), 3);
/** Rupees as typed -> whole paise, as the backend's to_paise. */
export const toPaise = (text: string) => toUnits(parseAmount(text), 2);
/** Tunch % as typed -> hundredths of a percent, as the backend's to_bp (91.666 -> 9167). */
export const toBp = (text: string) => toUnits(parseAmount(text), 2);

/** Fine mg = net mg × tunch ÷ 100, half up: the backend's fine_of, so the fine shown is the fine saved. */
export const fineOf = (netMg: number, tunchBp: number) => (netMg && tunchBp ? halfUp(netMg * tunchBp, 10000) : 0);

/**
 * Net and fine in whole mg, as the backend's item_weights: each input is first rounded to the mg, 0.001 ct
 * or 0.01 %; net = gross − (diamond + stone ct) × 0.2 g; fine = net × tunch ÷ 100.
 */
export function weights(item: { gross: string; diamond_ct: string; stone_ct: string; net: string; tunch: string }) {
  const carats = toUnits(parseAmount(item.diamond_ct), 3) + toUnits(parseAmount(item.stone_ct), 3);
  const gross = toMg(item.gross);
  const netMg = item.net.trim() ? toMg(item.net) : gross ? gross - halfUp(carats * 2, 10) : 0;
  const tunchBp = item.tunch.trim() ? toBp(item.tunch) : 0;
  return { netMg, tunchBp, fineMg: fineOf(netMg, tunchBp) };
}

/** GST on a taxable value in paise; an estimate, as the bill splits it into CGST + SGST or IGST. */
export const gstOn = (taxablePaise: number, rate: string) => halfUp(taxablePaise * toBp(rate), 10000);

/**
 * An opening balance (or opening metal) to send, signed by the Dr/Cr chosen beside the field (Cr = minus).
 * A minus sign, brackets or Dr/Cr typed in the field must agree with that choice: "-25,000" with Cr chosen
 * once went out as "--25000", which the backend reads as Dr. Throws a message for the user otherwise.
 */
export function signedOpening(text: string, side: string, what: string): string {
  const value = readAmount(text);
  if (Number.isNaN(value)) throw new Error(badNumber([[what, text]]) ?? `${what} is not a number.`);
  if (!value) return "0";
  const written = value < 0 ? "Cr" : /dr/i.test(text) ? "Dr" : null;
  if (written && written !== side) {
    throw new Error(`${what} "${text.trim()}" is written as ${written}, but ${side} is chosen beside it. Type the figure without a sign and choose Dr or Cr.`);
  }
  return `${side === "Cr" ? "-" : ""}${Math.abs(value)}`;
}

/**
 * One save at a time: a second tap while the first request is still out is ignored, so a slow
 * connection cannot post the same voucher twice. `saving` disables the button meanwhile.
 */
export function useSaving(): [boolean, (task: () => Promise<void>) => Promise<void>] {
  const busy = useRef(false);
  const [saving, setSaving] = useState(false);
  const run = useCallback(async (task: () => Promise<void>) => {
    if (busy.current) return;
    busy.current = true;
    setSaving(true);
    try {
      await task();
    } finally {
      busy.current = false;
      setSaving(false);
    }
  }, []);
  return [saving, run];
}

const INVALID = { borderColor: "var(--danger)", outlineColor: "var(--danger)" };

/** A number field that marks text the backend could not read. */
export function NumberInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "value"> & { value: string }) {
  const bad = unreadable(props.value);
  return <input inputMode="decimal" {...props} aria-invalid={bad || undefined} style={bad ? { ...props.style, ...INVALID } : props.style} />;
}

export function LedgerSelect({ ledgers, value, onChange, filter, placeholder }: {
  ledgers: Ledger[];
  value: string;
  onChange: (v: string) => void;
  filter?: (l: Ledger) => boolean;
  placeholder?: string;
}) {
  const list = filter ? ledgers.filter(filter) : ledgers;
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{placeholder ?? "Choose…"}</option>
      {list.map((l) => (
        <option key={l.id} value={l.id}>
          {l.name} ({l.group_name})
        </option>
      ))}
    </select>
  );
}

/** Confirmation after saving: every rupee and metal line of the new voucher. */
export function SavedVoucher({ voucher }: { voucher: VoucherDetail | null }) {
  if (!voucher) return null;
  const rupees = voucher.lines.map((l) => `${l.ledger} ${l.dr_paise ? "Dr" : "Cr"} ${formatValue((l.dr_paise || l.cr_paise) / 100, "money")}`);
  const metal = voucher.metal_lines
    .filter((m) => !m.item || voucher.metal_lines.length <= 3)
    .map((m) => `${m.ledger} ${m.dr_mg ? "Dr" : "Cr"} ${formatGrams((m.dr_mg || m.cr_mg) / 1000)} fine ${m.metal}`);
  return (
    <p className="verify verified">
      ✓ Saved {voucher.vtype} {voucher.number}: {[...rupees, ...metal].join(" · ")}
    </p>
  );
}

/** "owes you 12.345 g" / "you owe 1.000 g" / "nil" for a fine-metal balance in grams. */
export function metalBalanceText(grams: number | undefined): string {
  if (!grams) return "nil";
  return grams > 0 ? `owes you ${formatGrams(grams)} fine` : `you owe ${formatGrams(-grams)} fine`;
}
