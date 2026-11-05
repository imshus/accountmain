import type { HeadKey, ItemField } from "./form";

// The backend answers a rejected bill with one sentence (accounts/service.py, metal.py). Its wording names the
// field, so the message can sit under the box it is about instead of only at the bottom.
const RULES: [RegExp, HeadKey | ItemField][] = [
  [/books begin|locked period|locked up to|the date/i, "date"],
  [/(sales|purchase) number|document number|rule 46/i, "invoiceNo"],
  [/party ledger|ledger called|ledger a name/i, "party"],
  [/fine weight .*more than the net/i, "net"],
  [/gross weight/i, "gross"],
  [/net weight|fine weight/i, "net"],
  [/tunch|purity/i, "purity"],
  [/diamond carats/i, "diaCt"],
  [/diamond value/i, "diaValue"],
  [/stone carats/i, "stnCt"],
  [/stone value/i, "stnValue"],
  [/labour/i, "labourValue"],
];

/** Which field a backend message is about (a bill field, or an item field, whose item the message does not say), or null
 * for a message about the whole bill. */
export function fieldOf(message: string): HeadKey | ItemField | null {
  return RULES.find(([pattern]) => pattern.test(message))?.[1] ?? null;
}

export const isHeadKey = (key: HeadKey | ItemField): key is HeadKey => key === "date" || key === "invoiceNo" || key === "party";
