import { formatGrams, formatPaise } from "../../format";
import type { Report } from "../../types";

/** The design writes minus as "−" (U+2212), not a hyphen. */
const MINUS = "−";

/** Grams with 3 decimals and the design's signs: −4.350 g, +22.442 g (sign = true), 18.092 g. */
export function grams(value: number | null | undefined, sign = false): string {
  const g = value ?? 0;
  if (Math.abs(g) < 0.0005) return formatGrams(0);
  const text = formatGrams(Math.abs(g));
  return g < 0 ? `${MINUS}${text}` : sign ? `+${text}` : text;
}

const trimmed = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }); // as on the owner's screens: 25.65 g

/** A weight as the owner writes it, without trailing zeros: 20 g, 12.5 g, 18.32 g, −8 g; "ct" for diamonds. */
export function weightShort(value: number | null | undefined, unit: "g" | "ct" = "g"): string {
  const v = value ?? 0;
  if (Math.abs(v) < 0.0005) return `0 ${unit}`;
  return `${v < 0 ? MINUS : ""}${trimmed.format(Math.abs(v))} ${unit}`;
}

/** A voucher amount: whole rupees when there are no paise (₹28,438), else ₹26,543.10. */
export function voucherRupees(paise: number, sign: "+" | "−" | "" = ""): string {
  const text = formatPaise(Math.abs(paise), paise % 100 === 0 ? 0 : 2);
  return `${sign}${text}`;
}

/** A report card's value by the start of its label ("Closing" finds "Closing (fine)"). */
export function cardValue(report: Report | null, label: string): number {
  const card = report?.cards.find((c) => c.label.toLowerCase().startsWith(label.toLowerCase()));
  return typeof card?.value === "number" ? card.value : 0;
}

/** A YYYY-MM-DD date as the UTC midnight it names (NaN when it is not one), for counting days without time zones. */
export function utcDay(iso: string): number {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

/** The YYYY-MM-DD date `days` after (or before) `iso`. */
export function addDays(iso: string, days: number): string {
  return new Date(utcDay(iso) + days * 86_400_000).toISOString().slice(0, 10);
}
