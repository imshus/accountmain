import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import { useSession } from "./session";
import type { Ledger, Metal, Report, VoucherDetail, VoucherRow } from "./types";

/**
 * The current company's books as the quick screens (Sale/Purchase entry, Transactions, Stock, Reports) use them:
 * its ledgers, the latest entries, the name lists for quick entry, and saving / cancelling a jewellery bill.
 * Ported from the owner's React Native app (lib/ledger.tsx).
 */

export type EntryType = "sales" | "purchase";
export type MasterKind = "customer" | "supplier" | "salesman" | "purchaser" | "item" | "purity";

/** One jewellery line as typed on the Sale / Purchase screen. Weights in grams, rates in rupees. */
export type NewEntry = {
  type: EntryType;
  date: string; // YYYY-MM-DD
  invoiceNo: string; // "" = numbered by the books
  party: string;
  agent: string; // salesman (sale) / purchaser (purchase); kept in the narration
  item: string;
  grossWt: number;
  netWt: number;
  purity: number; // tunch %
  diamondCt: number;
  diamondRate: number; // ₹ per carat
  labourRate: number; // ₹ per gram of net weight
  metal?: Metal; // default gold
  gstRate?: number; // default 3 (jewellery)
};

/** Totals of a posted invoice, in paise; fine_by_weight_mg in milligrams. */
export type InvoiceSummary = { taxable: number; cgst?: number; sgst?: number; igst?: number; round_off?: number; total: number; fine_by_weight_mg?: number };
export type SavedEntry = { voucher: VoucherDetail; number: string; summary: InvoiceSummary };

export type BooksValue = {
  loading: boolean;
  error: string | null;
  ledgers: Ledger[];
  /** The latest entries (newest first), cancelled ones included. */
  vouchers: VoucherRow[];
  /** All entries in the books (vouchers may hold fewer). */
  voucherTotal: number;
  masters: Record<MasterKind, string[]>;
  addMaster: (kind: MasterKind, name: string) => void;
  saveJewellery: (entry: NewEntry) => Promise<SavedEntry>;
  /** Cancel an entry: it stays in the audit trail, marked cancelled. */
  cancel: (voucherId: number) => Promise<void>;
  refresh: () => Promise<void>;
  /** Bumped after every change (and refresh), so screens showing reports know to reload. */
  version: number;
  /** Tell the quick screens that the books changed elsewhere (e.g. an entry made in the full books). */
  changed: () => void;
};

export const GST_RATE_JEWELLERY = 3;
const VOUCHER_LIMIT = 200;
const PARTY_GROUP: Record<EntryType, string> = { sales: "Sundry Debtors", purchase: "Sundry Creditors" };

// Customers and suppliers are ledgers in the books; the other name lists are only for quick entry, kept on the device.
type LocalMasters = Record<"salesman" | "purchaser" | "item" | "purity", string[]>;
const MASTERS_KEY = "accountsai.masters";
const INITIAL_MASTERS: LocalMasters = { salesman: [], purchaser: [], item: [], purity: ["99.9", "91.6", "75", "58.5"] };

/** Tunch % -> karat code, so the stock report groups by karat (91.6 -> "22K"). */
const KARATS: [number, string][] = [
  [99.5, "24K"],
  [91.6, "22K"],
  [83.3, "20K"],
  [75, "18K"],
  [58.5, "14K"],
  [41.7, "10K"],
  [37.5, "9K"],
];
export function purityCode(tunch: number): string {
  const hit = KARATS.find(([t]) => Math.abs(t - tunch) <= 0.5);
  return hit ? hit[1] : `${tunch}`;
}

const sameName = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();
const addName = (list: string[], name: string) => (!name.trim() || list.some((n) => sameName(n, name)) ? list : [...list, name.trim()]);

function loadMasters(): LocalMasters {
  try {
    const saved = JSON.parse(localStorage.getItem(MASTERS_KEY) ?? "null") as Partial<LocalMasters> | null;
    return { ...INITIAL_MASTERS, ...(saved ?? {}) };
  } catch {
    return INITIAL_MASTERS;
  }
}

/** Today in the device's time zone, YYYY-MM-DD. */
export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** todayISO() that moves on at midnight and when the app comes back to the front, so a screen left open overnight
 * (a counter tablet) does not keep calling yesterday "Today". */
export function useToday(): string {
  const [today, setToday] = useState(todayISO);
  useEffect(() => {
    let timer = 0;
    const check = () => {
      setToday(todayISO());
      const now = new Date();
      const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
      window.clearTimeout(timer);
      timer = window.setTimeout(check, midnight.getTime() - now.getTime() + 1000);
    };
    const onShow = () => {
      if (document.visibilityState === "visible") check();
    };
    check();
    document.addEventListener("visibilitychange", onShow);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onShow);
    };
  }, []);
  return today;
}

const BooksContext = createContext<BooksValue | null>(null);

export function BooksProvider({ children }: { children: ReactNode }) {
  const { company, status, epoch } = useSession();
  const companyId = status === "ready" ? (company?.id ?? null) : null;
  const [ledgers, setLedgers] = useState<Ledger[]>([]);
  const [vouchers, setVouchers] = useState<VoucherRow[]>([]);
  const [voucherTotal, setVoucherTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [local, setLocal] = useState<LocalMasters>(loadMasters);
  // Party names typed but not yet in the books: the ledger is made when the first bill is saved.
  const [pending, setPending] = useState<Record<EntryType, string[]>>({ sales: [], purchase: [] });

  // The company now open. A refresh for one switched away from (e.g. an answer that finished after the switch) does
  // nothing, so it can never fill this company's books with another's ledgers and bills.
  const openId = useRef(companyId);
  openId.current = companyId;

  const refresh = useCallback(async () => {
    if (!companyId || openId.current !== companyId) return;
    setLoading(true);
    try {
      const [l, v] = await Promise.all([api.ledgers(companyId), api.vouchers(companyId, { limit: String(VOUCHER_LIMIT) })]);
      if (openId.current !== companyId) return;
      setLedgers(l);
      setVouchers(v.rows);
      setVoucherTotal(v.total);
      setError(null);
    } catch (e) {
      if (openId.current === companyId) setError((e as Error).message);
    } finally {
      if (openId.current === companyId) {
        setLoading(false);
        setVersion((n) => n + 1);
      }
    }
  }, [companyId]);

  useEffect(() => {
    setLedgers([]);
    setVouchers([]);
    setVoucherTotal(0);
    setLoading(false); // a refresh still running for the company before will not clear it
    void refresh();
  }, [refresh, epoch]);

  const addMaster = useCallback((kind: MasterKind, name: string) => {
    if (!name.trim()) return;
    if (kind === "customer" || kind === "supplier") {
      const type: EntryType = kind === "customer" ? "sales" : "purchase";
      setPending((cur) => ({ ...cur, [type]: addName(cur[type], name) }));
      return;
    }
    setLocal((cur) => {
      const next = { ...cur, [kind]: addName(cur[kind], name) };
      try {
        localStorage.setItem(MASTERS_KEY, JSON.stringify(next));
      } catch {
        // Kept for this session only.
      }
      return next;
    });
  }, []);

  const saveJewellery = useCallback(
    async (entry: NewEntry): Promise<SavedEntry> => {
      if (!companyId) throw new Error("Not connected to the server.");
      const isSale = entry.type === "sales";
      // A name already in the books (in any group) is reused: ledger names are unique per company.
      let party = ledgers.find((l) => sameName(l.name, entry.party));
      if (!party) party = await api.saveLedger(companyId, null, { name: entry.party.trim(), group: PARTY_GROUP[entry.type], opening: "0" });
      const voucher = await api.createJewellery(companyId, {
        vtype: isSale ? "Sales" : "Purchase",
        date: entry.date,
        number: entry.invoiceNo.trim() || null,
        party_id: party.id,
        metal: entry.metal ?? "gold",
        gst_rate: entry.gstRate ?? GST_RATE_JEWELLERY,
        items: [
          {
            item: entry.item.trim() || null,
            purity: purityCode(entry.purity),
            tunch: entry.purity,
            gross: entry.grossWt || null,
            net: entry.netWt,
            diamond_ct: entry.diamondCt || null,
            diamond_value: entry.diamondRate * entry.diamondCt || null,
            labour_rate: entry.labourRate || null,
            settle: "Wt",
          },
        ],
        narration: entry.agent.trim() ? `${isSale ? "Salesman" : "Purchaser"}: ${entry.agent.trim()}` : "",
      });
      setPending((cur) => ({ ...cur, [entry.type]: cur[entry.type].filter((n) => !sameName(n, entry.party)) }));
      if (entry.item.trim()) addMaster("item", entry.item);
      if (entry.agent.trim()) addMaster(isSale ? "salesman" : "purchaser", entry.agent);
      await refresh();
      return { voucher, number: voucher.number, summary: (voucher.summary ?? { taxable: 0, total: 0 }) as InvoiceSummary };
    },
    [companyId, ledgers, refresh, addMaster],
  );

  const cancel = useCallback(
    async (voucherId: number) => {
      if (!companyId) throw new Error("Not connected to the server.");
      await api.cancelVoucher(companyId, voucherId);
      await refresh();
    },
    [companyId, refresh],
  );

  const changed = useCallback(() => void refresh(), [refresh]);

  const masters = useMemo<Record<MasterKind, string[]>>(() => {
    const inGroup = (group: string) => ledgers.filter((l) => l.group_name === group).map((l) => l.name);
    return {
      customer: pending.sales.reduce(addName, inGroup(PARTY_GROUP.sales)),
      supplier: pending.purchase.reduce(addName, inGroup(PARTY_GROUP.purchase)),
      ...local,
    };
  }, [ledgers, pending, local]);

  const value = useMemo<BooksValue>(
    () => ({ loading, error, ledgers, vouchers, voucherTotal, masters, addMaster, saveJewellery, cancel, refresh, version, changed }),
    [loading, error, ledgers, vouchers, voucherTotal, masters, addMaster, saveJewellery, cancel, refresh, version, changed],
  );
  return <BooksContext.Provider value={value}>{children}</BooksContext.Provider>;
}

export function useBooks(): BooksValue {
  const value = useContext(BooksContext);
  if (!value) throw new Error("useBooks() must be used inside <BooksProvider>");
  return value;
}

/** A company report from the backend (e.g. "dashboard", "stock", "trial-balance"), reloaded whenever the books change. */
export function useCompanyReport(kind: string, params: Record<string, string> = {}) {
  const { company, status } = useSession();
  const { version } = useBooks();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const companyId = status === "ready" ? company?.id : undefined;
  const query = JSON.stringify(params);

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    try {
      setReport(await api.companyReport(companyId, kind, JSON.parse(query) as Record<string, string>));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [companyId, kind, query]);

  useEffect(() => {
    void load();
  }, [load, version]);

  return { report, loading, error, reload: load };
}
