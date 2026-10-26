import { useEffect, useState } from "react";
import { api } from "../../api";
import { formatGrams, formatValue } from "../../format";
import type { Company, Ledger, Metal, VoucherDetail } from "../../types";
import { Icon, Segmented } from "../../ui";
import {
  LedgerSelect, NumberInput, PARTIES, SavedVoucher, badNumber, fineOf, gstOn, halfUp, metalBalanceText, parseAmount, toBp, toMg, toPaise, today,
  useSaving, weights,
} from "./shared";

type Props = {
  company: Company;
  ledgers: Ledger[];
  onSaved: (voucher: VoucherDetail) => void;
};

type Item = {
  item: string;
  purity: string;
  gross: string;
  diamond_ct: string;
  stone_ct: string;
  net: string;
  tunch: string;
  diamond_value: string;
  stone_value: string;
  labour_rate: string;
  settle: "Wt" | "Rs";
};

const EMPTY_ITEM: Item = {
  item: "", purity: "", gross: "", diamond_ct: "", stone_ct: "", net: "", tunch: "", diamond_value: "", stone_value: "",
  labour_rate: "", settle: "Wt",
};


function MetalPicker({ value, onChange }: { value: Metal; onChange: (m: Metal) => void }) {
  return (
    <div className="field metal-field">
      <span>Metal</span>
      <Segmented
        variant="metal"
        label="Metal"
        value={value}
        onChange={onChange}
        options={[
          { value: "gold", label: "Gold" },
          { value: "silver", label: "Silver" },
        ]}
      />
    </div>
  );
}

/** The party's metal balance in grams. Each answer is kept with the party it is for, so after a quick
 * change from party A to B, A's slower answer is never shown as B's balance. */
function usePartyMetal(companyId: number, party: string, refresh: number) {
  const key = party ? `${companyId}/${party}` : "";
  const [loaded, setLoaded] = useState<{ key: string; balance: Partial<Record<Metal, number>> }>({ key: "", balance: {} });
  useEffect(() => {
    if (!key) return;
    let live = true;
    api.metalBalance(companyId, Number(party)).then(
      (balance) => live && setLoaded({ key, balance }),
      () => live && setLoaded({ key, balance: {} }),
    );
    return () => {
      live = false;
    };
    // key covers the company and party
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, refresh]);
  return loaded.key === key ? loaded.balance : {};
}

/** A sale or purchase of jewellery: each item's fine weight, settled by weight (Wt) or in rupees (Rs). */
export function JewelleryForm({ company, ledgers, onSaved }: Props) {
  const [vtype, setVtype] = useState<"Sales" | "Purchase">("Sales");
  const [date, setDate] = useState(today());
  const [number, setNumber] = useState("");
  const [party, setParty] = useState("");
  const [metal, setMetal] = useState<Metal>("gold");
  const [gst, setGst] = useState("3");
  const [rate, setRate] = useState("");
  const [items, setItems] = useState<Item[]>([{ ...EMPTY_ITEM }]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<VoucherDetail | null>(null);
  const [refresh, setRefresh] = useState(0);
  const balance = usePartyMetal(company.id, party, refresh);
  const sales = vtype === "Sales";
  const anyRs = items.some((i) => i.settle === "Rs");
  const [saving, guard] = useSaving();

  // In mg and paise with the backend's half-up steps (metal.jewellery_invoice), so the summary matches the saved bill.
  const totals = items.reduce(
    (t, item) => {
      const { netMg, fineMg } = weights(item);
      const metalValue = item.settle === "Rs" ? halfUp(fineMg * toPaise(rate), 1000) : 0;
      const value = metalValue + toPaise(item.diamond_value) + toPaise(item.stone_value) + halfUp(netMg * toPaise(item.labour_rate), 1000);
      return { fineWt: t.fineWt + (item.settle === "Wt" ? fineMg : 0), fineRs: t.fineRs + (item.settle === "Rs" ? fineMg : 0), value: t.value + value };
    },
    { fineWt: 0, fineRs: 0, value: 0 },
  );
  const tax = gstOn(totals.value, gst);
  const problem = badNumber([
    ...items.flatMap((i, n): [string, string][] => {
      const at = items.length > 1 ? ` (item ${n + 1})` : "";
      return [
        [`Gross g${at}`, i.gross], [`Diamond ct${at}`, i.diamond_ct], [`Stone ct${at}`, i.stone_ct], [`Net g${at}`, i.net],
        [`Tunch %${at}`, i.tunch], [`Diamond ₹${at}`, i.diamond_value], [`Stone ₹${at}`, i.stone_value], [`Labour ₹ per g${at}`, i.labour_rate],
      ];
    }),
    ["GST %", gst],
    ["Metal rate", anyRs ? rate : ""],
  ]);

  function set(index: number, patch: Partial<Item>) {
    setItems((all) => all.map((x, j) => (j === index ? { ...x, ...patch } : x)));
  }

  const save = () => guard(async () => {
    setError(null);
    try {
      const voucher = await api.createJewellery(company.id, {
        vtype, date, number: number || null, party_id: Number(party), metal, gst_rate: parseAmount(gst), metal_rate: rate || null,
        items: items.map((i) => ({ ...i, tunch: i.tunch.trim() ? parseAmount(i.tunch) : null, net: i.net.trim() || null })),
      });
      setSaved(voucher);
      setNumber("");
      setItems([{ ...EMPTY_ITEM, purity: items[0].purity, tunch: items[0].tunch, labour_rate: items[0].labour_rate }]);
      setRefresh((r) => r + 1);
      onSaved(voucher);
    } catch (e) {
      setError((e as Error).message);
    }
  });

  return (
    <div className="entry-grid">
      <div className="report-params">
        <label className="field">
          <span>Bill</span>
          <select value={vtype} onChange={(e) => { setVtype(e.target.value as "Sales" | "Purchase"); setParty(""); }}>
            <option value="Sales">Sale</option>
            <option value="Purchase">Purchase</option>
          </select>
        </label>
        <label className="field">
          <span>Date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field">
          <span>Bill no. (blank = next)</span>
          <input value={number} onChange={(e) => setNumber(e.target.value)} maxLength={16} />
        </label>
        <label className="field grow">
          <span>{sales ? "Customer" : "Supplier"}</span>
          <LedgerSelect ledgers={ledgers} value={party} onChange={setParty} filter={(l) => l.group_name === (sales ? "Sundry Debtors" : "Sundry Creditors")} />
        </label>
        <MetalPicker value={metal} onChange={setMetal} />
      </div>
      {party ? <p className="muted small">Metal account now: {metalBalanceText(balance[metal])}.</p> : null}

      {items.map((item, i) => {
        const { netMg, tunchBp, fineMg } = weights(item);
        return (
          <fieldset key={i} className="item-card">
            <legend>
              Item {i + 1}
              {items.length > 1 ? (
                <button className="icon-button" onClick={() => setItems((all) => all.filter((_, j) => j !== i))} aria-label={`Remove item ${i + 1}`}>
                  <Icon name="close" size={15} stroke={2.2} />
                </button>
              ) : null}
            </legend>
            <div className="item-fields">
              <label className="field wide">
                <span>Item</span>
                <input value={item.item} onChange={(e) => set(i, { item: e.target.value })} placeholder="Diamond ring" />
              </label>
              <label className="field">
                <span>Purity</span>
                <input value={item.purity} onChange={(e) => set(i, { purity: e.target.value })} placeholder="18K" />
              </label>
              <label className="field">
                <span>Gross g</span>
                <NumberInput value={item.gross} onChange={(e) => set(i, { gross: e.target.value })} />
              </label>
              <label className="field">
                <span>Diamond ct</span>
                <NumberInput value={item.diamond_ct} onChange={(e) => set(i, { diamond_ct: e.target.value })} />
              </label>
              <label className="field">
                <span>Stone ct</span>
                <NumberInput value={item.stone_ct} onChange={(e) => set(i, { stone_ct: e.target.value })} />
              </label>
              <label className="field">
                <span>Net g</span>
                <NumberInput value={item.net} placeholder={netMg ? (netMg / 1000).toFixed(3) : "auto"} onChange={(e) => set(i, { net: e.target.value })} />
              </label>
              <label className="field">
                <span>Tunch %</span>
                <NumberInput value={item.tunch} onChange={(e) => set(i, { tunch: e.target.value })} placeholder="76" />
              </label>
              <label className="field">
                <span>Diamond ₹</span>
                <NumberInput value={item.diamond_value} onChange={(e) => set(i, { diamond_value: e.target.value })} />
              </label>
              <label className="field">
                <span>Stone ₹</span>
                <NumberInput value={item.stone_value} onChange={(e) => set(i, { stone_value: e.target.value })} />
              </label>
              <label className="field">
                <span>Labour ₹ per g</span>
                <NumberInput value={item.labour_rate} onChange={(e) => set(i, { labour_rate: e.target.value })} />
              </label>
              <label className="field">
                <span>Metal settled</span>
                <select value={item.settle} onChange={(e) => set(i, { settle: e.target.value as "Wt" | "Rs" })}>
                  <option value="Wt">By weight (Wt)</option>
                  <option value="Rs">In rupees (Rs)</option>
                </select>
              </label>
            </div>
            <p className="item-result">
              Net {formatGrams(netMg / 1000)} × tunch {tunchBp ? tunchBp / 100 : "?"} ÷ 100 = <strong>{formatGrams(fineMg / 1000)} fine</strong>
              {tunchBp && toBp(item.tunch) / 100 !== parseAmount(item.tunch) ? " (tunch is kept to 2 decimals)" : ""}
            </p>
          </fieldset>
        );
      })}
      <div className="sql-actions">
        <button className="button small-button" onClick={() => setItems((all) => [...all, { ...EMPTY_ITEM, purity: all.at(-1)!.purity, tunch: all.at(-1)!.tunch, labour_rate: all.at(-1)!.labour_rate, settle: all.at(-1)!.settle }])}>
          + Add item
        </button>
      </div>
      <div className="report-params">
        <label className="field">
          <span>GST %</span>
          <NumberInput value={gst} onChange={(e) => setGst(e.target.value)} />
        </label>
        {anyRs ? (
          <label className="field">
            <span>Metal rate ₹ per g fine</span>
            <NumberInput value={rate} onChange={(e) => setRate(e.target.value)} />
          </label>
        ) : null}
      </div>
      <div className="entry-summary">
        {totals.fineWt ? <span>{sales ? "Customer owes" : "You owe supplier"} <strong>{formatGrams(totals.fineWt / 1000)} fine</strong> {metal}</span> : null}
        {totals.fineRs ? <span>Metal billed in rupees: {formatGrams(totals.fineRs / 1000)} fine</span> : null}
        <span>
          Value {formatValue(totals.value / 100, "money")} + GST {formatValue(tax / 100, "money")} ≈ <strong>{formatValue((totals.value + tax) / 100, "money")}</strong>
        </span>
      </div>
      {problem ? <div className="callout warning">{problem}</div> : null}
      <button className="button primary" onClick={() => void save()}
        disabled={saving || !party || Boolean(problem) || !items.some((i) => i.tunch && (i.gross || i.net))}>
        {saving ? "Saving…" : `Save ${sales ? "sale" : "purchase"}`}
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <SavedVoucher voucher={saved} />
    </div>
  );
}

/** Metal received from a party (old gold, bullion, settlement) or given to one (karigar issue, metal paid). */
export function MetalMoveForm({ company, ledgers, onSaved, direction = "Metal Receipt" }: Props & { direction?: "Metal Receipt" | "Metal Issue" }) {
  const [vtype, setVtype] = useState<"Metal Receipt" | "Metal Issue">(direction);
  const [date, setDate] = useState(today());
  const [party, setParty] = useState("");
  const [metal, setMetal] = useState<Metal>("gold");
  const [lines, setLines] = useState([{ item: "", net: "", tunch: "" }]);
  const [narration, setNarration] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<VoucherDetail | null>(null);
  const [refresh, setRefresh] = useState(0);
  const balance = usePartyMetal(company.id, party, refresh);
  const inward = vtype === "Metal Receipt";
  const [saving, guard] = useSaving();
  // Whole mg, as the backend rounds net and tunch before fine_of.
  const lineFine = (l: { net: string; tunch: string }) => fineOf(toMg(l.net), toBp(l.tunch));
  const total = lines.reduce((s, l) => s + lineFine(l), 0);
  const now = balance[metal] ?? 0;
  const after = (Math.round(now * 1000) + (inward ? -total : total)) / 1000;
  const problem = badNumber(lines.flatMap((l, n): [string, string][] => {
    const at = lines.length > 1 ? ` on line ${n + 1}` : "";
    return [[`Net g${at}`, l.net], [`Tunch %${at}`, l.tunch]];
  }));

  const save = () => guard(async () => {
    setError(null);
    try {
      const voucher = await api.createMetalMove(company.id, {
        vtype, date, party_id: Number(party), metal, narration,
        items: lines.filter((l) => l.net.trim()).map((l) => ({ item: l.item || null, net: l.net, tunch: parseAmount(l.tunch) || null })),
      });
      setSaved(voucher);
      setLines([{ item: "", net: "", tunch: lines[0].tunch }]);
      setRefresh((r) => r + 1);
      onSaved(voucher);
    } catch (e) {
      setError((e as Error).message);
    }
  });

  return (
    <div className="entry-grid">
      <div className="report-params">
        <label className="field">
          <span>Direction</span>
          <select value={vtype} onChange={(e) => setVtype(e.target.value as "Metal Receipt" | "Metal Issue")}>
            <option value="Metal Receipt">Received from party</option>
            <option value="Metal Issue">Given to party</option>
          </select>
        </label>
        <label className="field">
          <span>Date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field grow">
          <span>Party</span>
          <LedgerSelect ledgers={ledgers} value={party} onChange={setParty} filter={(l) => PARTIES.has(l.group_name)} />
        </label>
        <MetalPicker value={metal} onChange={setMetal} />
      </div>
      <table className="data-table compact">
        <thead>
          <tr>
            <th>Description</th>
            <th className="num">Net g</th>
            <th className="num">Tunch %</th>
            <th className="num">Fine g</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {lines.map((line, i) => (
            <tr key={i}>
              <td>
                <input value={line.item} placeholder="Old gold / bar" onChange={(e) => setLines((all) => all.map((x, j) => (j === i ? { ...x, item: e.target.value } : x)))} />
              </td>
              <td className="num">
                <NumberInput value={line.net} onChange={(e) => setLines((all) => all.map((x, j) => (j === i ? { ...x, net: e.target.value } : x)))} />
              </td>
              <td className="num">
                <NumberInput value={line.tunch} placeholder="99.5" onChange={(e) => setLines((all) => all.map((x, j) => (j === i ? { ...x, tunch: e.target.value } : x)))} />
              </td>
              <td className="num">{formatGrams(lineFine(line) / 1000)}</td>
              <td>
                {lines.length > 1 ? (
                  <button className="icon-button" onClick={() => setLines((all) => all.filter((_, j) => j !== i))} aria-label="Remove line">
                    <Icon name="close" size={15} stroke={2.2} />
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="sql-actions">
        <button className="button small-button" onClick={() => setLines((all) => [...all, { item: "", net: "", tunch: all.at(-1)!.tunch }])}>
          + Add line
        </button>
      </div>
      {party ? (
        <p className="entry-summary">
          <span>Now: {metalBalanceText(now)}</span>
          <span>
            After this: <strong>{metalBalanceText(after)}</strong>
          </span>
        </p>
      ) : null}
      <label className="field">
        <span>Narration</span>
        <input value={narration} onChange={(e) => setNarration(e.target.value)} />
      </label>
      {problem ? <div className="callout warning">{problem}</div> : null}
      <button className="button primary" onClick={() => void save()} disabled={saving || !party || total <= 0 || Boolean(problem)}>
        {saving ? "Saving…" : `Save ${inward ? "metal received" : "metal given"}`}
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <SavedVoucher voucher={saved} />
    </div>
  );
}

/** Convert metal a party owes (or is owed) into rupees at an agreed rate per fine gram. */
export function RateCutForm({ company, ledgers, onSaved }: Props) {
  const [date, setDate] = useState(today());
  const [party, setParty] = useState("");
  const [metal, setMetal] = useState<Metal>("gold");
  const [fine, setFine] = useState("");
  const [rate, setRate] = useState("");
  const [gst, setGst] = useState("3");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<VoucherDetail | null>(null);
  const [refresh, setRefresh] = useState(0);
  const balance = usePartyMetal(company.id, party, refresh);
  const owed = balance[metal] ?? 0;
  const withMetal = ledgers.filter((l) => l.metal?.[metal]?.closing_mg);
  const [saving, guard] = useSaving();
  // Paise from whole mg and paise, as metal.rate_cut computes the value.
  const fineMg = toMg(fine);
  const ratePaise = toPaise(rate);
  const value = halfUp(fineMg * ratePaise, 1000);
  const tax = gstOn(value, gst);
  const problem = badNumber([["Fine g", fine], ["Rate", rate], ["GST %", gst]]);

  const save = () => guard(async () => {
    setError(null);
    try {
      const voucher = await api.createRateCut(company.id, { date, party_id: Number(party), metal, fine, rate, gst_rate: parseAmount(gst) });
      setSaved(voucher);
      setFine("");
      setRefresh((r) => r + 1);
      onSaved(voucher);
    } catch (e) {
      setError((e as Error).message);
    }
  });

  return (
    <div className="entry-grid">
      <p className="muted small">
        A rate cut turns metal owed into rupees. If the party owes you metal, it becomes a sale at this rate; if you owe the party, a purchase.
      </p>
      <div className="report-params">
        <label className="field">
          <span>Date</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field grow">
          <span>Party</span>
          <LedgerSelect ledgers={withMetal.length ? withMetal : ledgers.filter((l) => PARTIES.has(l.group_name))} value={party}
            onChange={(v) => { setParty(v); setFine(""); }} placeholder={withMetal.length ? "Parties with a metal balance…" : "Choose…"} />
        </label>
        <MetalPicker value={metal} onChange={setMetal} />
      </div>
      {party ? (
        <p className="muted small">
          {metalBalanceText(owed)}
          {owed ? (
            <button className="link-button" onClick={() => setFine(Math.abs(owed).toFixed(3))}>
              {" "}Use all
            </button>
          ) : null}
        </p>
      ) : null}
      <div className="report-params">
        <label className="field">
          <span>Fine g to convert</span>
          <NumberInput value={fine} onChange={(e) => setFine(e.target.value)} />
        </label>
        <label className="field">
          <span>Rate ₹ per g fine</span>
          <NumberInput value={rate} onChange={(e) => setRate(e.target.value)} />
        </label>
        <label className="field">
          <span>GST %</span>
          <NumberInput value={gst} onChange={(e) => setGst(e.target.value)} />
        </label>
      </div>
      <p className="entry-summary">
        <span>
          {formatGrams(fineMg / 1000)} × ₹{(ratePaise / 100).toLocaleString("en-IN")} = {formatValue(value / 100, "money")}
        </span>
        <span>
          + GST {formatValue(tax / 100, "money")} ≈ <strong>{formatValue((value + tax) / 100, "money")}</strong> {owed < 0 ? "payable to the party" : "from the party"}
        </span>
      </p>
      {problem ? <div className="callout warning">{problem}</div> : null}
      <button className="button primary" onClick={() => void save()} disabled={saving || !party || fineMg <= 0 || ratePaise <= 0 || Boolean(problem)}>
        {saving ? "Saving…" : "Save rate cut"}
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <SavedVoucher voucher={saved} />
    </div>
  );
}
