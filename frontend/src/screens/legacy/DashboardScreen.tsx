import { useEffect } from "react";
import { useBooks } from "../../books";
import CompanyView from "../../components/accounts/CompanyView";
import { useLibrary } from "../../library";
import { useSession } from "../../session";
import LegacyFrame from "./LegacyFrame";

/** The full company books (menu → Dashboard): entries, GST returns, trial balance, P&L, balance sheet, bank, gold. */
export default function DashboardScreen({ tab }: { tab?: string }) {
  const { company, updateCompany, refreshCompanies } = useSession();
  const { books, datasets } = useLibrary();
  const { refresh } = useBooks();
  // Entries made here: the quick screens (Transactions, Stock, Reports) reload when leaving.
  useEffect(
    () => () => {
      void refresh();
      void refreshCompanies().catch(() => null);
    },
    [refresh, refreshCompanies],
  );
  return (
    <LegacyFrame title={company?.name ?? "Dashboard"} width="full" loading={!company}>
      {company ? (
        <CompanyView key={company.id} company={company} books={books} datasets={datasets} onCompanyChange={updateCompany} initialTab={tab} />
      ) : null}
    </LegacyFrame>
  );
}
