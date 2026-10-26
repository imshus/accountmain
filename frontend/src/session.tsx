import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, isApp, serverUrl } from "./api";
import type { Company, Health } from "./types";

/**
 * Which backend the app talks to and which company's books it shows. The backend address is VITE_API_URL from
 * frontend/.env (api.ts); the backend has no login, so the only thing kept on the device is the chosen company.
 */

export type SessionStatus = "connecting" | "ready" | "offline" | "no-server";

export type SessionValue = {
  /** "no-server": the Android app was built without VITE_API_URL, so it has no backend to talk to. */
  status: SessionStatus;
  /** Why the last connection failed (status "offline"). */
  error: string | null;
  health: Health | null;
  /** The AI the server has a key for, e.g. "GPT-6 Luna"; null when none is set up. */
  aiLabel: string | null;
  company: Company | null;
  companies: Company[];
  /** Bumped after every successful (re)connect: lists that come from the server reload on it. */
  epoch: number;
  selectCompany: (id: number) => void;
  /** Create a company and switch to it. */
  addCompany: (body: { name: string; gstin?: string; fy_start?: string }) => Promise<Company>;
  /** Put an edited company (from the books' settings) into the list. */
  updateCompany: (company: Company) => void;
  /** Re-read the companies (voucher counts change as entries are saved). */
  refreshCompanies: () => Promise<void>;
  retry: () => void;
};

const COMPANY_KEY = "accountsai.company";
const DEFAULT_COMPANY_NAME = "My Business";

function storedCompany(): number | null {
  try {
    const id = Number(localStorage.getItem(COMPANY_KEY));
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

function rememberCompany(id: number | null) {
  try {
    if (id) localStorage.setItem(COMPANY_KEY, String(id));
    else localStorage.removeItem(COMPANY_KEY);
  } catch {
    // Not saved: the first company is shown next time.
  }
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const server = serverUrl();
  const [status, setStatus] = useState<SessionStatus>(isApp && !server ? "no-server" : "connecting");
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState<number | null>(storedCompany());
  const [attempt, setAttempt] = useState(0);
  const [epoch, setEpoch] = useState(0);

  // Connect: the backend must answer, and there must be a company to keep the books in.
  useEffect(() => {
    if (isApp && !server) {
      setStatus("no-server");
      setHealth(null);
      setCompanies([]);
      return;
    }
    let stale = false;
    setStatus("connecting");
    setError(null);
    (async () => {
      try {
        const h = await api.health();
        let list = await api.companies();
        if (stale) return; // React's development double run: let only the live run create the first company
        if (!list.length) list = [{ ...(await api.createCompany({ name: DEFAULT_COMPANY_NAME })), voucher_count: 0 }];
        if (stale) return;
        setHealth(h);
        setCompanies(list);
        setCompanyId((id) => (id && list.some((c) => c.id === id) ? id : list[0].id));
        setStatus("ready");
        setEpoch((n) => n + 1);
      } catch (e) {
        if (stale) return;
        setHealth(null);
        setError((e as Error).message);
        setStatus("offline");
      }
    })();
    return () => {
      stale = true;
    };
  }, [server, attempt]);

  useEffect(() => {
    if (status === "ready") rememberCompany(companyId);
  }, [status, companyId]);

  const selectCompany = useCallback((id: number) => setCompanyId(id), []);

  const addCompany = useCallback(async (body: { name: string; gstin?: string; fy_start?: string }) => {
    const created = await api.createCompany(body);
    setCompanies((list) => [...list, { ...created, voucher_count: 0 }]);
    setCompanyId(created.id);
    return created;
  }, []);

  const updateCompany = useCallback((company: Company) => {
    setCompanies((list) => list.map((c) => (c.id === company.id ? { ...c, ...company } : c)));
  }, []);

  const refreshCompanies = useCallback(async () => {
    const list = await api.companies();
    setCompanies(list);
    setCompanyId((id) => (id && list.some((c) => c.id === id) ? id : (list[0]?.id ?? null)));
  }, []);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const value = useMemo<SessionValue>(() => {
    const ai = health?.providers.find((p) => p.id === health.default_provider && p.configured) ?? health?.providers.find((p) => p.configured);
    return {
      status,
      error,
      health,
      aiLabel: ai?.label ?? null,
      company: companies.find((c) => c.id === companyId) ?? null,
      companies,
      epoch,
      selectCompany,
      addCompany,
      updateCompany,
      refreshCompanies,
      retry,
    };
  }, [status, error, health, companies, companyId, epoch, selectCompany, addCompany, updateCompany, refreshCompanies, retry]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession() must be used inside <SessionProvider>");
  return value;
}

/** The current company, for screens that only render once connected (App shows them only when status is "ready"). */
export function useCompany(): Company {
  const { company } = useSession();
  if (!company) throw new Error("useCompany() used before a company was loaded");
  return company;
}

/** "Gupta Jewellers" -> "GJ", for the avatar. */
export function initialsOf(name: string | null | undefined): string {
  const words = (name ?? "").trim().split(/\s+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? "AI").slice(0, 2)).toUpperCase();
}
