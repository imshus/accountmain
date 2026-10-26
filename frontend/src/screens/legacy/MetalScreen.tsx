import { useBooks } from "../../books";
import { MetalMoveForm } from "../../components/accounts/MetalEntry";
import { navigate, type MetalKind } from "../../router";
import { useSession } from "../../session";
import { Segmented } from "../../ui";
import LegacyFrame from "./LegacyFrame";

/** Gold in / out (Home quick action): metal received from or given to a party, by fine weight. */
export default function MetalScreen({ kind }: { kind: MetalKind }) {
  const { company } = useSession();
  const { ledgers, refresh } = useBooks();
  return (
    <LegacyFrame title="Gold in / out" loading={!company}>
      <div className="legacy-switch">
        <Segmented
          label="Direction"
          value={kind}
          onChange={(next) => navigate({ name: "metal", kind: next }, { replace: true })}
          options={[
            { value: "receipt", label: "Received", icon: "down", tone: "mint" },
            { value: "issue", label: "Given", icon: "up", tone: "amber" },
          ]}
        />
      </div>
      {company ? (
        <section className="panel">
          <MetalMoveForm
            key={`${company.id}-${kind}`}
            company={company}
            ledgers={ledgers}
            direction={kind === "receipt" ? "Metal Receipt" : "Metal Issue"}
            onSaved={() => void refresh()}
          />
        </section>
      ) : null}
    </LegacyFrame>
  );
}
