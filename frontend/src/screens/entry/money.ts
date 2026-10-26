import { formatMg, formatPaise } from "../../format";

/** Paise as the entry screens show them: whole rupees without decimals (₹5,750), otherwise with paise (₹172.50). */
export const money = (paise: number) => formatPaise(paise, paise % 100 ? 2 : 0);

/** Milligrams as grams to 3 decimals (10.534 g). */
export const grams = (mg: number) => formatMg(mg);

/** Milligrams as a plain number to type over (11.500), no grouping or unit. */
export const gramsText = (mg: number) => (mg / 1000).toFixed(3);
