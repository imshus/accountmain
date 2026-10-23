import { useState } from "react";
import { api } from "../api";
import { decimalsOf, formatCount, formatFixed, groupExact } from "../format";
import type { ColumnCalcResult, DatasetDetail, Sheet } from "../types";
import { FormulaDetails } from "./ChatPanel";
import DataTable from "./DataTable";

type Props = {
  dataset: DatasetDetail;
  sheet: Sheet;
  onSheetChanged: (sheet: Sheet) => void;
};

/** Exact calculator for numbers, and formulas across columns (add, subtract, multiply, divide, check, save). */
export default function CalculatorPanel({ dataset, sheet, onSheetChanged }: Props) {
  const [expression, setExpression] = useState("");
  const [history, setHistory] = useState<{ expression: string; result: string }[]>([]);
  const [numberError, setNumberError] = useState<string | null>(null);

  const [formula, setFormula] = useState("");
  const [compareTo, setCompareTo] = useState("");
  const [tolerance, setTolerance] = useState("0.005");
  const [saveAs, setSaveAs] = useState("");
  const [result, setResult] = useState<ColumnCalcResult | null>(null);
  const [formulaError, setFormulaError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const numberColumns = sheet.profile.columns.filter((c) => c.kind === "number");
  // The result's own precision (from its preview column and stats), so weights keep 3 decimals.
  const places = result
    ? decimalsOf([...result.preview.rows.map((row) => row[row.length - 1]), result.stats.sum, result.stats.min, result.stats.max])
    : 0;

  async function calculate() {
    if (!expression.trim()) return;
    setNumberError(null);
    try {
      const out = await api.calc(expression);
      setHistory((h) => [out, ...h].slice(0, 10));
      setExpression("");
    } catch (e) {
      setNumberError((e as Error).message);
    }
  }

  async function runFormula(save: boolean) {
    if (!formula.trim()) return;
    setBusy(true);
    setFormulaError(null);
    try {
      const out = await api.columnCalc(dataset.id, sheet.table_name, {
        expression: formula,
        ...(compareTo ? { compare_to: compareTo, tolerance: Number(tolerance) || 0 } : {}),
        ...(save ? { save_as: saveAs } : {}),
      });
      setResult(out);
      if (out.sheet) {
        onSheetChanged(out.sheet);
        setSaveAs("");
      }
    } catch (e) {
      setFormulaError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function insert(name: string) {
    setFormula((f) => (f && !/[\s(+\-*/]$/.test(f) ? `${f} + ${name}` : `${f}${name}`));
  }

  return (
    <div className="calc-grid">
      <section className="panel">
        <h2>Calculator</h2>
        <p className="muted small">Exact decimal arithmetic: 0.1 + 0.2 is exactly 0.3. Accepts 1,23,456.78, ₹, % and brackets.</p>
        <form
          className="ask-form"
          onSubmit={(e) => {
            e.preventDefault();
            void calculate();
          }}
        >
          <input className="calc-input" value={expression} onChange={(e) => setExpression(e.target.value)} placeholder="e.g. 1,06,32,762.45 - 29,22,754.52 + 1000 * 18%" aria-label="Calculation" />
          <button className="button primary" type="submit">
            =
          </button>
        </form>
        {numberError ? <p className="error-text small">{numberError}</p> : null}
        <ul className="calc-history">
          {history.map((h, i) => (
            <li key={i}>
              {/* The exact result with Indian grouping, every decimal kept (10.125 * 0.916 = 9.2745, not 9.27). */}
              <span className="muted">{h.expression} =</span> <strong>{groupExact(h.result)}</strong>{" "}
              <code className="muted small">{h.result}</code>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Column formula</h2>
        <p className="muted small">
          Add, subtract, multiply or divide columns row by row, e.g. <code>credit - debit</code> or <code>taxable_value + cgst + sgst</code>. Blank cells count as 0.
        </p>
        <div className="chips">
          {numberColumns.map((c) => (
            <button key={c.name} className="chip mono" onClick={() => insert(c.name)} title={c.label}>
              {c.name}
            </button>
          ))}
        </div>
        <textarea className="sql-input" rows={2} value={formula} onChange={(e) => setFormula(e.target.value)} placeholder="credit - debit" aria-label="Column formula" spellCheck={false} />
        <div className="report-params">
          <label className="field">
            <span>Check against column (optional)</span>
            <select value={compareTo} onChange={(e) => setCompareTo(e.target.value)}>
              <option value="">—</option>
              {numberColumns.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          {compareTo ? (
            <label className="field">
              <span>Tolerance</span>
              <input type="number" step="any" min="0" value={tolerance} onChange={(e) => setTolerance(e.target.value)} />
            </label>
          ) : null}
          <button className="button primary" onClick={() => void runFormula(false)} disabled={busy || !formula.trim()}>
            {busy ? "Working…" : "Calculate"}
          </button>
        </div>
        {formulaError ? <div className="callout warning">{formulaError}</div> : null}
        {result ? (
          <>
            <div className="cards">
              {(
                [
                  ["Rows", result.stats.count, 0],
                  ["Sum", result.stats.sum, places],
                  ["Average", result.stats.mean, Math.max(places, 2)],
                  ["Smallest", result.stats.min, places],
                  ["Largest", result.stats.max, places],
                ] as const
              ).map(([label, value, decimals]) => {
                const text = value === null ? "—" : formatFixed(value, decimals);
                return (
                  <div className="card stat" key={label}>
                    <span className="stat-label">{label}</span>
                    <span className={`stat-value${text.startsWith("-") ? " negative" : ""}`}>{text}</span>
                  </div>
                );
              })}
            </div>
            {result.check ? (
              <div className="queries">
                <FormulaDetails check={{ ...result.check, error: null }} />
                <p className={`verify ${result.check.mismatches ? "unverified" : "verified"}`}>
                  {result.check.mismatches
                    ? `! ${formatCount(result.check.mismatches ?? 0)} of ${formatCount(result.check.rows_checked ?? 0)} rows do not match.`
                    : `✓ The formula matches all ${formatCount(result.check.rows_checked ?? 0)} rows.`}
                </p>
              </div>
            ) : null}
            <DataTable columns={result.preview.columns} rows={result.preview.rows} />
            {result.saved_column ? <p className="verify verified">✓ Saved as a new column: {result.saved_column}. Totals and reports now include it.</p> : null}
            <form
              className="report-params"
              onSubmit={(e) => {
                e.preventDefault();
                void runFormula(true);
              }}
            >
              <label className="field">
                <span>Save the result as a new column</span>
                <input value={saveAs} onChange={(e) => setSaveAs(e.target.value)} placeholder="e.g. Net amount" />
              </label>
              <button className="button" type="submit" disabled={busy || !saveAs.trim()}>
                Save column
              </button>
            </form>
          </>
        ) : null}
      </section>
    </div>
  );
}
