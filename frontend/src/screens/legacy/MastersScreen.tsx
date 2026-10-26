import { useEffect, useId, useMemo, useState } from "react";
import { api } from "../../api";
import { useBooks, type MasterKind } from "../../books";
import LedgersPanel from "../../components/accounts/LedgersPanel";
import { formatMg, formatPaise } from "../../format";
import { useSession } from "../../session";
import type { AccountsMeta } from "../../types";
import { Badge, Button, EmptyState, Field, Icon, Input, Notice, Page, Segmented, Sheet } from "../../ui";
import "./legacy.css";

type View = "customers" | "suppliers" | "lists" | "all";
const GROUP: Record<"customers" | "suppliers", string> = { customers: "Sundry Debtors", suppliers: "Sundry Creditors" };
const LISTS: { kind: Exclude<MasterKind, "customer" | "supplier">; title: string }[] = [
  { kind: "salesman", title: "Sales men" },
  { kind: "purchaser", title: "Purchasers" },
  { kind: "item", title: "Items" },
  { kind: "purity", title: "Purity %" },
];

/** Menu → Masters: customers, suppliers, the quick-entry name lists, and every ledger of the books. */
export default function MastersScreen() {
  const [view, setView] = useState<View>("customers");
  return (
    <Page title="Masters" width="wide">
      <div className="legacy-switch">
        <Segmented
          label="Masters"
          value={view}
          onChange={setView}
          options={[
            { value: "customers", label: "Customers" },
            { value: "suppliers", label: "Suppliers" },
            { value: "lists", label: "Lists" },
            { value: "all", label: "All ledgers" },
          ]}
        />
      </div>
      {view === "customers" || view === "suppliers" ? <Parties key={view} view={view} /> : view === "lists" ? <Lists /> : <AllLedgers />}
    </Page>
  );
}

function Parties({ view }: { view: "customers" | "suppliers" }) {
  const { company } = useSession();
  const { ledgers, refresh, error } = useBooks();
  const [filter, setFilter] = useState("");
  const [adding, setAdding] = useState(false);
  const list = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return ledgers.filter((l) => l.group_name === GROUP[view] && (!needle || l.name.toLowerCase().includes(needle)));
  }, [ledgers, view, filter]);
  const noun = view === "customers" ? "customer" : "supplier";

  return (
    <>
      <div className="masters-tools">
        <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={`Search ${view}`} aria-label={`Search ${view}`} type="search" />
        <Button variant="brand" icon="plus" onClick={() => setAdding(true)}>
          Add
        </Button>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {list.length ? (
        <ul className="lib-list masters-list">
          {list.map((l) => {
            const gold = l.metal?.gold?.closing_mg ?? 0;
            return (
              <li key={l.id} className="lib-row">
                <div className="lib-row__main">
                  <span className="lib-row__icon">
                    <Icon name="user" size={18} />
                  </span>
                  <span className="lib-row__text">
                    <strong>{l.name}</strong>
                    <span>{l.gstin ? `GSTIN ${l.gstin}` : "No GSTIN"}</span>
                  </span>
                  <span className="masters-amt">
                    <strong>
                      {formatPaise(Math.abs(l.closing_paise))} {l.closing_paise > 0 ? "Dr" : l.closing_paise < 0 ? "Cr" : ""}
                    </strong>
                    {gold ? (
                      <span>
                        {formatMg(Math.abs(gold))} fine {gold > 0 ? "owed to us" : "we owe"}
                      </span>
                    ) : null}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState icon="user" title={filter ? `No ${noun} matches` : `No ${view} yet`}>
          {filter ? "Try another name." : `A ${noun} is added here, or when you save their first bill.`}
        </EmptyState>
      )}
      {company ? (
        <AddParty
          open={adding}
          onClose={() => setAdding(false)}
          noun={noun}
          onSave={async (name, gstin) => {
            await api.saveLedger(company.id, null, { name, group: GROUP[view], opening: "0", gstin: gstin || undefined });
            await refresh();
          }}
        />
      ) : null}
    </>
  );
}

function AddParty({ open, onClose, noun, onSave }: { open: boolean; onClose: () => void; noun: string; onSave: (name: string, gstin: string) => Promise<void> }) {
  const [name, setName] = useState("");
  const [gstin, setGstin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  const gstinId = useId();
  useEffect(() => {
    if (open) {
      setName("");
      setGstin("");
      setError(null);
    }
  }, [open]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await onSave(name.trim(), gstin.trim());
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={`New ${noun}`}
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" busy={busy} disabled={!name.trim()} onClick={() => void save()}>
            Save
          </Button>
        </>
      }
    >
      <div className="masters-form">
        <Field label="Name" htmlFor={nameId}>
          <Input id={nameId} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} data-autofocus />
        </Field>
        <Field label="GSTIN (optional)" htmlFor={gstinId}>
          <Input id={gstinId} value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} maxLength={15} placeholder="07ABCDE1234F1Z5" />
        </Field>
        {error ? <Notice tone="error">{error}</Notice> : null}
      </div>
    </Sheet>
  );
}

function Lists() {
  const { masters, addMaster } = useBooks();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  return (
    <div className="masters-lists">
      <p className="lib-empty">These names fill the Sale and Purchase forms. They are kept on this device.</p>
      {LISTS.map(({ kind, title }) => (
        <section key={kind} className="lib-section" aria-label={title}>
          <h2 className="ui-overline">{title}</h2>
          <div className="masters-chips">
            {masters[kind].length ? masters[kind].map((name) => <Badge key={name}>{name}</Badge>) : <span className="lib-empty">None yet</span>}
          </div>
          <form
            className="masters-tools"
            onSubmit={(e) => {
              e.preventDefault();
              addMaster(kind, drafts[kind] ?? "");
              setDrafts((d) => ({ ...d, [kind]: "" }));
            }}
          >
            <Input
              value={drafts[kind] ?? ""}
              onChange={(e) => setDrafts((d) => ({ ...d, [kind]: e.target.value }))}
              placeholder={`Add to ${title.toLowerCase()}`}
              aria-label={`Add to ${title}`}
              inputMode={kind === "purity" ? "decimal" : undefined}
            />
            <Button type="submit" variant="soft" disabled={!(drafts[kind] ?? "").trim()}>
              Add
            </Button>
          </form>
        </section>
      ))}
    </div>
  );
}

function AllLedgers() {
  const { company, updateCompany } = useSession();
  const { ledgers, refresh } = useBooks();
  const [meta, setMeta] = useState<AccountsMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.accountsMeta().then(setMeta, (e: Error) => setError(e.message));
  }, []);
  if (error) return <Notice tone="error">{error}</Notice>;
  if (!company) return null;
  return (
    <div className="legacy">
      <LedgersPanel company={company} ledgers={ledgers} groups={meta?.groups ?? []} onChanged={() => void refresh()} onCompanyChange={updateCompany} />
    </div>
  );
}
