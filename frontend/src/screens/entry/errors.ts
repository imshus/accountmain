import type { FieldKey } from "./form";

// The backend answers a rejected bill with one sentence (accounts/service.py, metal.py). Its wording names the
// field, so the message can sit under the box it is about instead of only at the bottom.
const RULES: [RegExp, FieldKey][] = [
  [/books begin|locked period|locked up to|the date/i, "date"],
  [/(sales|purchase) number|document number|rule 46/i, "invoiceNo"],
  [/party ledger|ledger called|ledger a name/i, "party"],
  [/fine weight .*more than the net/i, "net"],
  [/gross weight/i, "gross"],
  [/net weight|fine weight/i, "net"],
  [/tunch|purity/i, "purity"],
  [/diamond carats/i, "diamondCt"],
  [/diamond value/i, "diamondRate"],
  [/stone carats/i, "stoneCt"],
  [/stone value/i, "stoneRate"],
  [/labour/i, "labourRate"],
  [/metal rate|metal value/i, "metalRate"],
  [/gst rate|gst_rate/i, "gst"],
];

/** Which field a backend message is about, or null for a message about the whole bill. */
export function fieldOf(message: string): FieldKey | null {
  return RULES.find(([pattern]) => pattern.test(message))?.[1] ?? null;
}
