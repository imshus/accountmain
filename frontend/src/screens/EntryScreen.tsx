import { useState, type FormEvent, type KeyboardEvent } from "react";
import { navigate, type EntryKind } from "../router";
import { Page, Segmented } from "../ui";
import { AddNameSheet, type AddRequest } from "./entry/AddNameSheet";
import { DetailsCard } from "./entry/DetailsCard";
import { SavedSheet } from "./entry/SavedSheet";
import { useEntry } from "./entry/useEntry";
import { WeightCard } from "./entry/WeightCard";
import "./entry/entry.css";

export type EntryScreenProps = { kind: EntryKind };

const FOCUSABLE = "input:not([type=hidden]):not([disabled]), select:not([disabled]), button.entry-picker__btn";

/** Enter in a box moves to the next one (the phone keyboard's "Next"); only the Save button saves. */
function enterMovesOn(event: KeyboardEvent<HTMLFormElement>) {
  const target = event.target as HTMLElement;
  if (event.key !== "Enter" || !(target instanceof HTMLInputElement) || target.type === "search" || target.type === "date") return;
  event.preventDefault();
  const all = [...event.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
  all[all.indexOf(target) + 1]?.focus();
}

/** Sale / Purchase entry (design: sales.html, purchase.html): one jewellery bill posted to the books. */
export default function EntryScreen({ kind }: EntryScreenProps) {
  const entry = useEntry(kind);
  const [request, setRequest] = useState<AddRequest | null>(null);
  const sale = kind === "sale";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void entry.save();
  };

  return (
    <Page title={sale ? "Sales entry" : "Purchase entry"}>
      <div className="entry">
        <Segmented
          label="Entry type"
          value={kind}
          onChange={(next) => navigate({ name: "entry", kind: next }, { replace: true })}
          options={[
            { value: "sale", label: "Sale", icon: "trend", tone: "mint" },
            { value: "purchase", label: "Purchase", icon: "cart", tone: "amber" },
          ]}
        />
        <form className="entry__form" onSubmit={submit} onKeyDown={enterMovesOn} noValidate aria-busy={entry.saving || undefined}>
          <DetailsCard entry={entry} kind={kind} ask={setRequest} />
          <WeightCard entry={entry} kind={kind} ask={setRequest} />
        </form>
      </div>
      {/* Outside the form: React events from a portal still bubble through the form in the component tree. */}
      <AddNameSheet request={request} onClose={() => setRequest(null)} />
      <SavedSheet
        saved={entry.saved}
        kind={kind}
        onNew={() => {
          entry.setSaved(null);
          // After the sheet hands focus back to Save: start the next bill at the top.
          requestAnimationFrame(() => {
            document.getElementById(entry.idOf("party"))?.focus({ preventScroll: true });
            window.scrollTo({ top: 0, behavior: "smooth" });
          });
        }}
        onDone={() => {
          entry.setSaved(null);
          navigate({ name: "transactions" }, { replace: true });
        }}
      />
    </Page>
  );
}
