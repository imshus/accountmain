import { useMemo } from "react";
import type { Route } from "../../router";
import { useSession } from "../../session";
import type { Report } from "../../types";
import { grams } from "./figures";
import { useBooksReport } from "./useBooksReport";

export type BookWarning = {
  id: string;
  level: "warning" | "error";
  message: string;
  action?: { label: string; to: Route };
};

type KaratRow = { karat?: unknown; fine_net?: unknown };

/** Metals the books hold, read from the dashboard's "Gold stock (fine g)" style cards. */
export function metalsInUse(dashboard: Report | null): ("gold" | "silver")[] {
  const labels = (dashboard?.cards ?? []).map((c) => c.label.toLowerCase());
  return (["gold", "silver"] as const).filter((metal) => labels.some((l) => l.startsWith(`${metal} stock`)));
}

/** A karat sold beyond what came in, and the stock report's own warnings. The Stock screen lists them too. */
export function stockWarnings(metal: "gold" | "silver", report: Report | null): BookWarning[] {
  if (!report) return [];
  const name = metal === "gold" ? "Gold" : "Silver";
  const rows = (report.tables[0]?.rows ?? []) as KaratRow[];
  const negative: BookWarning[] = rows
    .filter((r) => typeof r.fine_net === "number" && r.fine_net < -0.0005)
    .map((r) => ({
      id: `stock-${metal}-${String(r.karat)}`,
      level: "warning",
      message: `${name} ${String(r.karat)}: ${grams(r.fine_net as number)} fine. Sales purchase se zyada hai — purchase entry check karo.`,
      action: { label: "Open stock", to: { name: "stock", metal } },
    }));
  return [...negative, ...checkWarnings(`stock-${metal}`, report, { label: "Open stock", to: { name: "stock", metal } })];
}

function checkWarnings(prefix: string, report: Report | null, action: BookWarning["action"]): BookWarning[] {
  // The server may also send "error" checks, though the type lists only ok / info / warning.
  return (report?.checks ?? [])
    .map((c) => ({ level: c.level as string, message: c.message }))
    .filter((c) => c.level === "warning" || c.level === "error")
    .map((c, i) => ({ id: `${prefix}-check-${i}`, level: c.level === "error" ? "error" : "warning", message: c.message, action }));
}

/**
 * What the bell lists: warnings from the report checks (books out of balance, negative stock by karat) and a
 * server with no AI key. Empty means the bell shows no dot.
 */
export function useBookWarnings() {
  const { status, aiLabel } = useSession();
  const dashboard = useBooksReport("dashboard");
  const metals = metalsInUse(dashboard.report);
  const hasGold = metals.includes("gold");
  const hasSilver = metals.includes("silver");
  const gold = useBooksReport("stock_grams", { metal: "gold" }, hasGold);
  const silver = useBooksReport("stock_grams", { metal: "silver" }, hasSilver);

  const warnings = useMemo<BookWarning[]>(() => {
    const out: BookWarning[] = [];
    if (status === "ready" && !aiLabel) {
      out.push({ id: "ai", level: "warning", message: "The server has no AI key set, so the chat cannot answer. Add one in the backend's .env file." });
    }
    out.push(...checkWarnings("dashboard", dashboard.report, { label: "Open reports", to: { name: "dashboard", tab: "reports" } }));
    if (hasGold) out.push(...stockWarnings("gold", gold.report));
    if (hasSilver) out.push(...stockWarnings("silver", silver.report));
    return out;
  }, [status, aiLabel, dashboard.report, hasGold, hasSilver, gold.report, silver.report]);

  return { warnings, loading: dashboard.loading || gold.loading || silver.loading };
}
