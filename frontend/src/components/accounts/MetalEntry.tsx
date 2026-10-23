import { useEffect, useState } from "react";
import { api } from "../../api";
import { formatGrams, formatValue } from "../../format";
import type { Company, Ledger, Metal, VoucherDetail } from "../../types";
import { LedgerSelect, PARTIES, SavedVoucher, metalBalanceText, parseAmount, roundTo, today } from "./shared";

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

/** Net = gross − (diamond + stone ct) × 0.2; fine = net × tunch ÷ 100 (3 decimals, as the backend computes). */
function weights(item: Item) {
  const net = item.net ? parseAmount(item.net) : roundTo(parseAmount(item.gross) - (parseAmount(item.diamond_ct) + parseAmount(item.stone_ct)) * 0.2, 3);
  const fine = item.tunch ? roundTo((net * parseAmount(item.tunch)) / 100, 3) : 0;
  return { net, fine };
}

function MetalPicker({ value, onChange }: { value: Metal; onChange: (m: Metal) => void }) {
  return (
    <label className="field">
      <span>Metal</span>
      <select value={value} onChange={(e) => onChange(e.target.value as Metal)}>
        <option value="gold">Gold</option>
        <option value="silver">Silver</option>
      </select>
    </label>
  );
}

function usePartyMetal(companyId: number, party: string, refresh: number) {
  const [balance, setBalance] = useState<Partial<Record<Metal, number>>>({});
  useEffect(() => {
    if (!party) return setBalance({});
    api.metalBalance(companyId, Number(party)).then(setBalance, () => setBalance({}));
  }, [companyId, party, refresh]);
  return balance;
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

  const totals = items.reduce(
    (t, item) => {
      const { net, fine } = weights(item);
      const metalValue = item.settle === "Rs" ? roundTo(fine * parseAmount(rate), 2) : 0;
      const value = metalValue + parseAmount(item.diamond_value) + parseAmount(item.stone_value) + roundTo(net * parseAmount(item.labour_rate), 2);
      return { fineWt: t.fineWt + (item.settle === "Wt" ? fine : 0), fineRs: t.fineRs + (item.settle === "Rs" ? fine : 0), value: t.value + value };
    },
    { fineWt: 0, fineRs: 0, value: 0 },
  );
  const tax = roundTo((totals.value * parseAmount(gst)) / 100, 2);

  function set(index: number, patch: Partial<Item>) {
    setItems((all) => all.map((x, j) => (j === index ? { ...x, ...patch } : x)));
  }

  async function save() {
    setError(null);
    try {
      const voucher = await api.createJewellery(company.id, {
        vtype, date, number: number || null, party_id: Number(party), metal, gst_rate: parseAmount(gst), metal_rate: rate || null,
        items: items.map((i) => ({ ...i, tunch: i.tunch ? parseAmount(i.tunch) : null, net: i.net || null })),
      });
      setSaved(voucher);
      setNumber("");
      setItems([{ ...EMPTY_ITEM, purity: items[0].purity, tunch: items[0].tunch, labour_rate: items[0].labour_rate }]);
      setRefresh((r) => r + 1);
      onSaved(voucher);
    } catch (e) {
      setError((e as Error).message);
    }
  }

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
        const { net, fine } = weights(item);
        return (
          <fieldset key={i} className="item-card">
            <legend>
              Item {i + 1}
              {items.length > 1 ? (
                <button className="icon-button" onClick={() => setItems((all) => all.filter((_, j) => j !== i))} aria-label={`Remove item ${i + 1}`}>
                  ×
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
                <input inputMode="decimal" value={item.gross} onChange={(e) => set(i, { gross: e.target.value })} />
              </label>
              <label className="field">
                <span>Diamond ct</span>
                <input inputMode="decimal" value={item.diamond_ct} onChange={(e) => set(i, { diamond_ct: e.target.value })} />
              </label>
              <label className="field">
                <span>Stone ct</span>
                <input inputMode="decimal" value={item.stone_ct} onChange={(e) => set(i, { stone_ct: e.target.value })} />
              </label>
              <label className="field">
                <span>Net g</span>
                <input inputMode="decimal" value={item.net} placeholder={net ? net.toFixed(3) : "auto"} onChange={(e) => set(i, { net: e.target.value })} />
              </label>
              <label className="field">
                <span>Tunch %</span>
                <input inputMode="decimal" value={item.tunch} onChange={(e) => set(i, { tunch: e.target.value })} placeholder="76" />
              </label>
              <label className="field">
                <span>Diamond ₹</span>
                <input inputMode="decimal" value={item.diamond_value} onChange={(e) => set(i, { diamond_value: e.target.value })} />
              </label>
              <label className="field">
                <span>Stone ₹</span>
                <input inputMode="decimal" value={item.stone_value} onChange={(e) => set(i, { stone_value: e.target.value })} />
              </label>
              <label className="field">
                <span>Labour ₹ per g</span>
                <input inputMode="decimal" value={item.labour_rate} onChange={(e) => set(i, { labour_rate: e.target.value })} />
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
              Net {formatGrams(net)} × tunch {item.tunch || "?"} ÷ 100 = <strong>{formatGrams(fine)} fine</strong>
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
          <input inputMode="decimal" value={gst} onChange={(e) => setGst(e.target.value)} />
        </label>
        {anyRs ? (
          <label className="field">
            <span>Metal rate ₹ per g fine</span>
            <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} />
          </label>
        ) : null}
      </div>
      <div className="entry-summary">
        {totals.fineWt ? <span>{sales ? "Customer owes" : "You owe supplier"} <strong>{formatGrams(totals.fineWt)} fine</strong> {metal}</span> : null}
        {totals.fineRs ? <span>Metal billed in rupees: {formatGrams(totals.fineRs)} fine</span> : null}
        <span>
          Value {formatValue(totals.value, "money")} + GST {formatValue(tax, "money")} ≈ <strong>{formatValue(totals.value + tax, "money")}</strong>
        </span>
      </div>
      <button className="button primary" onClick={() => void save()} disabled={!party || !items.some((i) => i.tunch && (i.gross || i.net))}>
        Save {sales ? "sale" : "purchase"}
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <SavedVoucher voucher={saved} />
    </div>
  );
}

/** Metal received from a party (old gold, bullion, settlement) or given to one (karigar issue, metal paid). */
export function MetalMoveForm({ company, ledgers, onSaved }: Props) {
  const [vtype, setVtype] = useState<"Metal Receipt" | "Metal Issue">("Metal Receipt");
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
  const fineOf = (l: { net: string; tunch: string }) => roundTo((parseAmount(l.net) * parseAmount(l.tunch)) / 100, 3);
  const total = lines.reduce((s, l) => s + fineOf(l), 0);
  const now = balance[metal] ?? 0;
  const after = roundTo(inward ? now - total : now + total, 3);

  async function save() {
    setError(null);
    try {
      const voucher = await api.createMetalMove(company.id, {
        vtype, date, party_id: Number(party), metal, narration,
        items: lines.filter((l) => l.net).map((l) => ({ item: l.item || null, net: l.net, tunch: parseAmount(l.tunch) || null })),
      });
      setSaved(voucher);
      setLines([{ item: "", net: "", tunch: lines[0].tunch }]);
      setRefresh((r) => r + 1);
      onSaved(voucher);
    } catch (e) {
      setError((e as Error).message);
    }
  }

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
                <input inputMode="decimal" value={line.net} onChange={(e) => setLines((all) => all.map((x, j) => (j === i ? { ...x, net: e.target.value } : x)))} />
              </td>
              <td className="num">
                <input inputMode="decimal" value={line.tunch} placeholder="99.5" onChange={(e) => setLines((all) => all.map((x, j) => (j === i ? { ...x, tunch: e.target.value } : x)))} />
              </td>
              <td className="num">{formatGrams(fineOf(line))}</td>
              <td>
                {lines.length > 1 ? (
                  <button className="icon-button" onClick={() => setLines((all) => all.filter((_, j) => j !== i))} aria-label="Remove line">
                    ×
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
      <button className="button primary" onClick={() => void save()} disabled={!party || total <= 0}>
        Save {inward ? "metal received" : "metal given"}
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
  const value = roundTo(parseAmount(fine) * parseAmount(rate), 2);
  const tax = roundTo((value * parseAmount(gst)) / 100, 2);

  async function save() {
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
  }

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
          <input inputMode="decimal" value={fine} onChange={(e) => setFine(e.target.value)} />
        </label>
        <label className="field">
          <span>Rate ₹ per g fine</span>
          <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} />
        </label>
        <label className="field">
          <span>GST %</span>
          <input inputMode="decimal" value={gst} onChange={(e) => setGst(e.target.value)} />
        </label>
      </div>
      <p className="entry-summary">
        <span>
          {formatGrams(parseAmount(fine))} × ₹{parseAmount(rate).toLocaleString("en-IN")} = {formatValue(value, "money")}
        </span>
        <span>
          + GST {formatValue(tax, "money")} ≈ <strong>{formatValue(value + tax, "money")}</strong> {owed < 0 ? "payable to the party" : "from the party"}
        </span>
      </p>
      <button className="button primary" onClick={() => void save()} disabled={!party || !parseAmount(fine) || !parseAmount(rate)}>
        Save rate cut
      </button>
      {error ? <div className="callout warning">{error}</div> : null}
      <SavedVoucher voucher={saved} />
    </div>
  );
}
