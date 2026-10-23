import { formatGrams, formatValue } from "../../format";
import type { Ledger, VoucherDetail } from "../../types";

export const CASH_BANK = new Set(["Cash-in-Hand", "Bank Accounts", "Bank OD A/c"]);
export const PARTIES = new Set(["Sundry Debtors", "Sundry Creditors"]);

export const today = () => new Date().toISOString().slice(0, 10);

/** "1,23,456.50" or "₹ 500" -> number; anything unreadable -> 0. */
export function parseAmount(text: string): number {
  const value = Number(text.replace(/[₹,\s]/g, ""));
  return Number.isFinite(value) ? value : 0;
}

/** Round half away from zero to `places` decimals, as the backend (and Excel) do. */
export function roundTo(value: number, places: number): number {
  const factor = 10 ** places;
  return (Math.sign(value) * Math.round(Math.abs(value) * factor + 1e-9)) / factor;
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
