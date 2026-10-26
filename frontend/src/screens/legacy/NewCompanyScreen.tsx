import NewCompany from "../../components/accounts/NewCompany";
import { back, navigate } from "../../router";
import { useSession } from "../../session";
import LegacyFrame from "./LegacyFrame";

/** Add another company (its own books). It becomes the current company. */
export default function NewCompanyScreen() {
  const { refreshCompanies, selectCompany } = useSession();
  return (
    <LegacyFrame title="New company" width="narrow">
      <NewCompany
        onCreated={(company) => {
          void refreshCompanies().then(() => {
            selectCompany(company.id);
            navigate({ name: "dashboard" }, { replace: true });
          });
        }}
        onCancel={() => back()}
      />
    </LegacyFrame>
  );
}
