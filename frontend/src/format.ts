import type { Cell, ValueFormat } from "./types";

// Indian digit grouping (1,23,45,678.90), matching the books this app is built for.
const money = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const count = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("en-IN", { style: "percent", maximumFractionDigits: 1 });
// Jewellery weights: grams and carats to the milligram / thousandth, as the trade writes them.
const weight = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

export type Format = ValueFormat | "drcr" | "date" | "group" | "weight" | "weight_drcr" | "carat";

const fixed = new Map<number, Intl.NumberFormat>();

/** 0 for anything that shows as zero at `decimals` places, so -0 and -0.001 never print as "-0.00".
 *  (signDisplay "negative" would do this, but older Android WebViews reject it.) */
function unsignedZero(value: number, decimals: number): number {
  return Math.abs(value) < 0.5 * 10 ** -decimals ? 0 : value;
}

/** Indian grouping with exactly `decimals` places (analysis results carry their own precision). */
export function formatFixed(value: number, decimals: number): string {
  let format = fixed.get(decimals);
  if (!format) {
    format = new Intl.NumberFormat("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    fixed.set(decimals, format);
  }
  return format.format(unsignedZero(value, decimals));
}

export function formatGrams(grams: number): string {
  return `${weight.format(unsignedZero(grams, 3))} g`;
}

/** Indian grouping for an exact decimal string ("-1234567.0125" -> "-12,34,567.0125"), keeping every digit. */
export function groupExact(text: string): string {
  const match = /^([-+]?)(\d+)(\.\d+)?$/.exec(text.trim());
  if (!match) return text;
  const [, sign, whole, fraction = ""] = match;
  const digits = whole.replace(/^0+(?=\d)/, "");
  const grouped = digits.length <= 3 ? digits : `${digits.slice(0, -3).replace(/\B(?=(\d{2})+$)/g, ",")},${digits.slice(-3)}`;
  const zero = /^0+$/.test(digits) && /^\.?0*$/.test(fraction);
  return `${sign === "-" && !zero ? "-" : ""}${grouped}${fraction}`;
}

const dateTime = new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" });

/** `decimals` sets the places of a "number" (a report column's own precision); without it a "number"
 *  keeps the digits it has (up to 4), so 1,234.568 g is not cut to 1,234.57. */
export function formatValue(value: unknown, format: Format, decimals?: number): string {
  if (value === null || value === undefined || value === "") return "—";
  if (format === "date" && typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)) return formatDate(value.slice(0, 10));
  if (typeof value !== "number") return String(value);
  switch (format) {
    case "drcr": {
      const v = unsignedZero(value, 2);
      return v === 0 ? "0.00" : `${money.format(Math.abs(v))} ${v > 0 ? "Dr" : "Cr"}`;
    }
    case "weight":
      return formatGrams(value);
    case "weight_drcr": {
      const v = unsignedZero(value, 3);
      return v === 0 ? "0.000 g" : `${formatGrams(Math.abs(v))} ${v > 0 ? "Dr" : "Cr"}`;
    }
    case "carat":
      return `${weight.format(unsignedZero(value, 3))} ct`;
    case "money":
      return money.format(unsignedZero(value, 2));
    case "count":
      return count.format(unsignedZero(value, 0));
    case "percent":
      return percent.format(unsignedZero(value, 3));
    case "number":
      return formatFixed(value, decimals ?? decimalsOf([value]));
    default:
      return String(value);
  }
}

/** Cells from SQL results and previews: numbers get grouping (and `decimals` places when given), the rest as-is. */
export function formatCell(value: Cell, decimals: boolean | number = false): string {
  if (value === null) return "—";
  if (typeof value === "number") {
    if (typeof decimals === "number") return formatFixed(value, decimals);
    return decimals ? money.format(unsignedZero(value, 2)) : count.format(unsignedZero(value, 0));
  }
  return String(value);
}

/** Decimals that show every number of a column exactly: 0 for whole numbers, else 2-4
 *  (rupees keep .00; weights keep their third decimal, 142.438 not 142.44). */
export function decimalsOf(values: unknown[]): number {
  let most = 0;
  for (const v of values) {
    if (typeof v === "number" && Number.isFinite(v) && !Number.isInteger(v)) {
      // Through toFixed(4) first, so float noise (0.30000000000000004) does not count as digits.
      const text = String(Number(v.toFixed(4)));
      most = Math.max(most, text.includes("e") ? 4 : Math.min(text.split(".")[1]?.length ?? 0, 4));
      if (most === 4) break;
    }
  }
  return most === 0 ? 0 : Math.max(2, most);
}

/** Column names that hold reference numbers, not amounts: invoice/bill/voucher no, HSN/SAC, codes,
 *  mobile, PIN, year, GSTIN. Matched on the whole name, so "Amount this year" stays an amount. */
const ID_NAME = new RegExp(
  "^(?:" +
    "(?:invoice|inv|bill|voucher|vch|vou|receipt|rcpt|challan|order|ref|reference|doc|document|serial|sr|s|cheque|chq|entry|txn|transaction|utr|account|ac|a c|folio)(?: ?(?:no|nos|num|number|#))" +
    "|(?:.* )?(?:hsn|sac|hsn sac|code|mobile|phone|contact|pin|pincode|zip|gstin|gstin uin|gst no|gst number|pan|aadhaar|aadhar|id)(?: (?:no|num|number|code))?" +
    "|year|fy|financial year|yr" +
  ")$",
);

export function isIdentifierName(name: string): boolean {
  const key = name.toLowerCase().replace(/[^a-z0-9#]+/g, " ").trim();
  return ID_NAME.test(key);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatTimestamp(iso: string): string {
  return dateTime.format(new Date(iso));
}

export function formatDate(isoDate: string): string {
  return dateOnly.format(new Date(`${isoDate}T00:00:00`));
}

export function formatCount(value: number): string {
  return count.format(unsignedZero(value, 0));
}
