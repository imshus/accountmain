import { useId, useState, type FormEvent, type KeyboardEvent } from "react";
import { navigate, type EntryKind } from "../router";
import { Button, Notice, Page } from "../ui";
import { AddNameSheet, type AddRequest } from "./entry/AddNameSheet";
import { DEFAULT_ITEMS } from "./entry/form";
import { HeaderCard } from "./entry/HeaderCard";
import { ItemCards } from "./entry/ItemCards";
import { SavedSheet } from "./entry/SavedSheet";
import { TotalCard } from "./entry/TotalCard";
import { sameName, useEntry } from "./entry/useEntry";
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

/** Sale / Purchase entry (design: accounts-ai-design-mockup, "Sales report" / "Purchase report"): one jewellery bill of
 * one or more items, posted to the books. */
export default function EntryScreen({ kind }: EntryScreenProps) {
  const entry = useEntry(kind);
  const [request, setRequest] = useState<AddRequest | null>(null);
  const itemList = useId();
  const sale = kind === "sale";
  const names = [...entry.books.masters.item, ...DEFAULT_ITEMS].filter((name, i, all) => all.findIndex((n) => sameName(n, name)) === i);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void entry.save();
  };

  const addMore = () => {
    const id = entry.addItem();
    // After React has drawn the new item: bring its first box into view and focus it.
    requestAnimationFrame(() => {
      const node = document.getElementById(entry.idOf(`${id}:name`));
      node?.scrollIntoView({ behavior: "smooth", block: "center" });
      node?.focus({ preventScroll: true });
    });
  };

  return (
    <Page title={sale ? "Sales report" : "Purchase report"}>
      <form className="entry entry__form" onSubmit={submit} onKeyDown={enterMovesOn} noValidate aria-busy={entry.saving || undefined}>
        <HeaderCard entry={entry} kind={kind} ask={setRequest} />
        {entry.form.items.map((item, index) => (
          <ItemCards key={item.id} entry={entry} ask={setRequest} item={item} index={index} itemList={itemList} />
        ))}
        <datalist id={itemList}>
          {names.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
        <TotalCard figures={entry.figures} />
        {entry.general ? <Notice tone="error">{entry.general}</Notice> : null}
        <div className="entry-actions">
          <Button variant="plain" size="lg" onClick={addMore}>
            Add more item
          </Button>
          <Button
            variant="primary"
            size="lg"
            type="submit"
            busy={entry.saving}
            className={entry.ready ? undefined : "is-idle"}
            aria-describedby={entry.ready ? undefined : `${itemList}-why`}
          >
            {entry.saving ? "Saving…" : sale ? "Save sales" : "Save purchase"}
          </Button>
        </div>
        {entry.ready ? null : (
          <p className="entry-note" id={`${itemList}-why`}>
            {sale ? "Choose the customer" : "Choose the supplier"} and name every item to save
          </p>
        )}
      </form>
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
