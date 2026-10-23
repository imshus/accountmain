import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { formatCount, formatFixed, formatValue } from "../format";
import type { Agg, AnalysisField, AnalysisResult, AnalysisSpec, AnalysisTable, Bucket, FilterOp, ReportTable } from "../types";
import ChecksList from "./ChecksList";
import { downloadCsv, MoreRows, useRowLimit } from "./ReportTableView";

type Props = {
  loadTables: () => Promise<AnalysisTable[]>;
  run: (spec: AnalysisSpec) => Promise<AnalysisResult>;
  /** A request to open with, e.g. one the AI made in the chat. */
  initialSpec?: AnalysisSpec | null;
};

const AGG_LABEL: Record<Agg, string> = {
  sum: "Total of", count: "Number of rows", average: "Average of", min: "Lowest", max: "Highest", distinct: "Number of different",
};
const BUCKET_LABEL: Record<Exclude<Bucket, "none">, string> = { day: "by day", month: "by month", quarter: "by quarter", fy: "by financial year", year: "by year" };
const OPS: Record<AnalysisField["kind"], [FilterOp, string][]> = {
  text: [["=", "is"], ["!=", "is not"], ["contains", "contains"], ["in", "is one of"], ["blank", "is blank"], ["not_blank", "is not blank"]],
  number: [["=", "="], ["!=", "≠"], [">", ">"], [">=", "≥"], ["<", "<"], ["<=", "≤"], ["between", "between"], ["blank", "is blank"], ["not_blank", "is not blank"]],
  date: [["=", "on"], ["<", "before"], [">", "after"], ["between", "between"], ["blank", "is blank"], ["not_blank", "is not blank"]],
};
const MONEY = /taxable|amount|amt|total|value|val\b|fine|debit|credit|balance/i;
const PARTY = /party|customer|supplier|account|ledger|name|item|category|head/i;

function defaultSpec(table: AnalysisTable): AnalysisSpec {
  const numbers = table.fields.filter((f) => f.kind === "number");
  const measure = numbers.find((f) => MONEY.test(f.name) || MONEY.test(f.label)) ?? numbers[0];
  const texts = table.fields.filter((f) => f.kind === "text");
  const group = texts.find((f) => PARTY.test(f.name) || PARTY.test(f.label)) ?? texts[0];
  const date = table.fields.find((f) => f.kind === "date");
  return {
    table: table.table,
    measures: measure ? [{ agg: "sum", column: measure.name }, { agg: "count", column: "" }] : [{ agg: "count", column: "" }],
    group_by: group ? [{ column: group.name, bucket: "none" }] : date ? [{ column: date.name, bucket: "month" }] : [],
    filters: [],
    sort: null,
    limit: group ? 10 : 0,
    across: false,
  };
}

/** Every condition has the values it needs, so the request can run as it stands. */
function complete(spec: AnalysisSpec): boolean {
  return spec.filters.every((f) =>
    f.op === "blank" || f.op === "not_blank" ? true : f.op === "in" ? f.values.length > 0 : f.op === "between" ? Boolean(f.value && f.value2) : Boolean(f.value),
  );
}

/** "Ram Lal, Shyam" -> ["Ram Lal", "Shyam"] for an "is one of" condition. */
function splitList(text: string): string[] {
  return text.split(",").map((x) => x.trim()).filter(Boolean);
}

function display(value: string | number | null | undefined, format: string, decimals = 0): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return format === "date" ? formatValue(value, "date") : value;
  return format === "number" ? formatFixed(value, decimals) : String(value);
}

/** Group, total and filter a table without writing SQL (DuckDB + pandas on the server, exact decimals). */
export default function AnalysePanel({ loadTables, run, initialSpec }: Props) {
  const [tables, setTables] = useState<AnalysisTable[] | null>(null);
  const [spec, setSpec] = useState<AnalysisSpec | null>(initialSpec ?? null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Only the latest request may update the screen (answers can arrive out of order while options change).
  const latest = useRef(0);

  const show = useCallback(async (next: AnalysisSpec) => {
    const id = ++latest.current;
    setBusy(true);
    try {
      const answer = await run(next);
      if (id !== latest.current) return;
      setResult(answer);
      setError(null);
    } catch (e) {
      if (id !== latest.current) return;
      setError((e as Error).message);
    } finally {
      if (id === latest.current) setBusy(false);
    }
  }, [run]);

  // Update as soon as an option changes (after a short pause, so typing a value sends one request).
  const specText = JSON.stringify(spec);
  const loaded = tables !== null;
  useEffect(() => {
    if (!loaded || !spec || !complete(spec)) return;
    const timer = window.setTimeout(() => void show(spec), 250);
    return () => window.clearTimeout(timer);
    // specText stands for spec; the first result is fetched by the loading effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specText, loaded]);

  useEffect(() => {
    let live = true;
    loadTables().then(
      (list) => {
        if (!live) return;
        const start = initialSpec ?? (list[0] ? defaultSpec(list[0]) : null);
        setSpec(start);
        setTables(list);  // the update effect then runs the first request
      },
      (e: Error) => live && setError(e.message),
    );
    return () => {
      live = false;
    };
    // Load once per panel; a new initialSpec remounts the panel (see the key where it is used).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const table = tables?.find((t) => t.table === spec?.table);
  const fields = useMemo(() => new Map((table?.fields ?? []).map((f) => [f.name, f])), [table]);
  if (!tables || !spec) return <section className="panel">{error ? <div className="callout warning">{error}</div> : <p className="muted small">Loading…</p>}</section>;

  const update = (patch: Partial<AnalysisSpec>) => setSpec((s) => (s ? { ...s, ...patch } : s));
  const options = (filter: (f: AnalysisField) => boolean) =>
    (table?.fields ?? []).filter(filter).map((f) => (
      <option key={f.name} value={f.name}>
        {f.label}
      </option>
    ));
  const g0 = spec.group_by[0];
  const g1 = spec.group_by[1];

  return (
    <section className="panel analyse">
      <div className="panel-heading">
        <h2>Analyse</h2>
        {tables.length > 1 ? (
          <select value={spec.table} aria-label="Table" onChange={(e) => {
            const next = tables.find((t) => t.table === e.target.value);
            if (next) setSpec(defaultSpec(next));
          }}>
            {tables.map((t) => (
              <option key={t.table} value={t.table}>
                {t.title}
              </option>
            ))}
          </select>
        ) : null}
      </div>

      <form className="analyse-builder" onSubmit={(e) => { e.preventDefault(); void show(spec); }}>
        <div className="builder-row">
          <span className="builder-label">Show</span>
          <div className="builder-items">
            {spec.measures.map((m, i) => (
              <span className="builder-item" key={i}>
                <select value={m.agg} aria-label="Measure" onChange={(e) => {
                  const agg = e.target.value as Agg;
                  const keep = fields.get(m.column);
                  const fits = agg === "count" ? false : agg === "distinct" ? true : agg === "min" || agg === "max" ? keep?.kind !== "text" : keep?.kind === "number";
                  const fallback = (table?.fields ?? []).find((f) => (agg === "distinct" ? true : agg === "min" || agg === "max" ? f.kind !== "text" : f.kind === "number"));
                  update({ measures: spec.measures.map((x, j) => (j === i ? { agg, column: agg === "count" ? "" : fits ? m.column : fallback?.name ?? "" } : x)) });
                }}>
                  {(Object.keys(AGG_LABEL) as Agg[]).map((a) => (
                    <option key={a} value={a}>
                      {AGG_LABEL[a]}
                    </option>
                  ))}
                </select>
                {m.agg !== "count" ? (
                  <select value={m.column} aria-label="Column" onChange={(e) => update({ measures: spec.measures.map((x, j) => (j === i ? { ...x, column: e.target.value } : x)) })}>
                    {options((f) => (m.agg === "distinct" ? true : m.agg === "min" || m.agg === "max" ? f.kind !== "text" : f.kind === "number"))}
                  </select>
                ) : null}
                {spec.measures.length > 1 ? (
                  <button type="button" className="icon-button" aria-label="Remove" onClick={() => update({ measures: spec.measures.filter((_, j) => j !== i) })}>
                    ×
                  </button>
                ) : null}
              </span>
            ))}
            {spec.measures.length < 4 ? (
              <button type="button" className="link-button" onClick={() => update({ measures: [...spec.measures, { agg: "count", column: "" }] })}>
                + Add
              </button>
            ) : null}
          </div>
        </div>

        <div className="builder-row">
          <span className="builder-label">Grouped by</span>
          <div className="builder-items">
            <span className="builder-item">
              <select value={g0?.column ?? ""} aria-label="Group by" onChange={(e) => {
                const f = fields.get(e.target.value);
                update({ group_by: e.target.value ? [{ column: e.target.value, bucket: f?.kind === "date" ? "month" : "none" }, ...spec.group_by.slice(1)] : [], across: false, limit: e.target.value ? spec.limit : 0 });
              }}>
                <option value="">Nothing (one total)</option>
                {options(() => true)}
              </select>
              {g0 && fields.get(g0.column)?.kind === "date" ? (
                <select value={g0.bucket} aria-label="Date grouping" onChange={(e) => update({ group_by: [{ ...g0, bucket: e.target.value as Bucket }, ...spec.group_by.slice(1)] })}>
                  {Object.entries(BUCKET_LABEL).map(([b, label]) => (
                    <option key={b} value={b}>
                      {label}
                    </option>
                  ))}
                </select>
              ) : null}
            </span>
            {g0 ? (
              <span className="builder-item">
                <span className="muted small">then</span>
                <select value={g1?.column ?? ""} aria-label="Then by" onChange={(e) => {
                  const f = fields.get(e.target.value);
                  update({ group_by: e.target.value ? [g0, { column: e.target.value, bucket: f?.kind === "date" ? "month" : "none" }] : [g0], across: e.target.value ? spec.across : false });
                }}>
                  <option value="">—</option>
                  {options((f) => f.name !== g0.column)}
                </select>
                {g1 && fields.get(g1.column)?.kind === "date" ? (
                  <select value={g1.bucket} aria-label="Date grouping" onChange={(e) => update({ group_by: [g0, { ...g1, bucket: e.target.value as Bucket }] })}>
                    {Object.entries(BUCKET_LABEL).map(([b, label]) => (
                      <option key={b} value={b}>
                        {label}
                      </option>
                    ))}
                  </select>
                ) : null}
                {g1 ? (
                  <label className="check-field">
                    <input type="checkbox" checked={spec.across} onChange={(e) => update({ across: e.target.checked })} /> side by side
                  </label>
                ) : null}
              </span>
            ) : null}
          </div>
        </div>

        <div className="builder-row">
          <span className="builder-label">Only where</span>
          <div className="builder-items">
            {spec.filters.map((flt, i) => {
              const f = fields.get(flt.column);
              const kind = f?.kind ?? "text";
              const set = (patch: Partial<AnalysisSpec["filters"][number]>) =>
                update({ filters: spec.filters.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
              const input = (value: string, onChange: (v: string) => void, label: string) => (
                <input aria-label={label} type={kind === "date" ? "date" : "text"} inputMode={kind === "number" ? "decimal" : undefined}
                  value={value} onChange={(e) => onChange(e.target.value)} placeholder={flt.op === "in" ? "A, B, C" : ""} />
              );
              return (
                <span className="builder-item" key={i}>
                  <select value={flt.column} aria-label="Filter column" onChange={(e) => set({ column: e.target.value, op: (OPS[fields.get(e.target.value)?.kind ?? "text"][0][0]), value: "", value2: "", values: [] })}>
                    {options(() => true)}
                  </select>
                  <select value={flt.op} aria-label="Condition" onChange={(e) => {
                    const op = e.target.value as FilterOp;
                    set(op === "in" && flt.op !== "in" ? { op, values: splitList(flt.value) } : { op });
                  }}>
                    {OPS[kind].map(([op, label]) => (
                      <option key={op} value={op}>
                        {label}
                      </option>
                    ))}
                  </select>
                  {/* The typed text is kept as typed (in value) so commas and spaces survive; the list is derived from it. */}
                  {flt.op === "in"
                    ? input(flt.value || flt.values.join(", "), (v) => set({ value: v, values: splitList(v) }), "Values")
                    : flt.op !== "blank" && flt.op !== "not_blank"
                      ? input(flt.value, (v) => set({ value: v }), "Value")
                      : null}
                  {flt.op === "between" ? (
                    <>
                      <span className="muted small">and</span>
                      {input(flt.value2, (v) => set({ value2: v }), "Second value")}
                    </>
                  ) : null}
                  <button type="button" className="icon-button" aria-label="Remove condition" onClick={() => update({ filters: spec.filters.filter((_, j) => j !== i) })}>
                    ×
                  </button>
                </span>
              );
            })}
            {spec.filters.length < 8 && table?.fields.length ? (
              <button type="button" className="link-button" onClick={() => {
                const f = table.fields.find((x) => x.kind === "date") ?? table.fields[0];
                update({ filters: [...spec.filters, { column: f.name, op: OPS[f.kind][0][0], value: "", value2: "", values: [] }] });
              }}>
                + Add condition
              </button>
            ) : null}
          </div>
        </div>

        <div className="builder-row">
          <span className="builder-label">Order</span>
          <div className="builder-items">
            <select value={spec.sort ?? ""} aria-label="Order" onChange={(e) => update({ sort: (e.target.value || null) as AnalysisSpec["sort"] })}>
              <option value="">Automatic</option>
              <option value="value_desc">Largest first</option>
              <option value="value_asc">Smallest first</option>
              <option value="label">A to Z / date order</option>
            </select>
            {g0 && !spec.across ? (
              <select value={spec.limit} aria-label="How many" onChange={(e) => update({ limit: Number(e.target.value) })}>
                <option value={0}>Show all</option>
                {[5, 10, 20, 50].map((n) => (
                  <option key={n} value={n}>
                    Top {n} + others
                  </option>
                ))}
              </select>
            ) : null}
            <span className="muted small analyse-status" aria-live="polite">
              {busy ? "Updating…" : spec && !complete(spec) ? "Fill in the condition to update" : ""}
            </span>
          </div>
        </div>
      </form>

      {error ? <div className="callout warning">{error}</div> : null}
      {result ? <AnalysisView result={result} /> : null}
    </section>
  );
}

/** The result: what was asked in words, the proof checks, a bar chart of the first measure and the table.
 *  Memoised so that changing the options above does not redraw a long result while the next one loads. */
export const AnalysisView = memo(function AnalysisView({ result, compact = false }: { result: AnalysisResult; compact?: boolean }) {
  const valueColumn = result.columns.find((c) => c.key === "m0" && c.format === "number");
  const grouped = result.columns[0]?.key === "g0" && result.rows.length > 1;
  const table: ReportTable = {
    title: result.description,
    columns: result.columns.map((c) => ({ key: c.key, label: c.label, format: c.format === "number" ? "number" : c.format })),
    rows: result.rows,
    total: result.total,
  };
  const [limit, showMore] = useRowLimit(result.rows);
  const rows = result.rows.slice(0, compact ? 10 : limit);
  return (
    <div className="analysis-result">
      <div className="report-head">
        <p className="analysis-description">
          <strong>{result.description}</strong>
          <span className="muted small">
            {" "}· {formatCount(result.rows_matched)} row{result.rows_matched === 1 ? "" : "s"} counted
            {result.groups ? ` · ${formatCount(result.groups)} groups` : ""}
          </span>
        </p>
        {!compact ? (
          <button className="button small-button" onClick={() => void downloadCsv(table, `${result.description}.csv`)}>
            Download CSV
          </button>
        ) : null}
      </div>
      {!compact ? <ChecksList checks={result.checks} title="Checks" /> : null}
      {!compact && grouped && valueColumn ? <BarChart result={result} decimals={valueColumn.decimals ?? 0} /> : null}
      <div className="table-scroll">
        <table className="data-table compact">
          <thead>
            <tr>
              {result.columns.map((c) => (
                <th key={c.key} className={c.format === "number" ? "num" : undefined}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={row._kind === "others" ? "row-others" : undefined}>
                {result.columns.map((c) => (
                  <td key={c.key} className={c.format === "number" ? "num" : undefined}>
                    {display(row[c.key], c.format, c.decimals)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          {result.total ? (
            <tfoot>
              <tr className="row-total">
                {result.columns.map((c) => (
                  <td key={c.key} className={c.format === "number" ? "num" : undefined}>
                    {c.key === result.columns[0].key ? "Total" : display(result.total?.[c.key], c.format, c.decimals)}
                  </td>
                ))}
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
      {compact && result.rows.length > rows.length ? <p className="muted small">{result.rows.length - rows.length} more rows</p> : null}
      {!compact ? <MoreRows shown={rows.length} total={result.rows.length} onMore={showMore} /> : null}
    </div>
  );
});

/** One series of horizontal bars (the first measure), grown from a shared baseline; hover or focus shows the value. */
function BarChart({ result, decimals }: { result: AnalysisResult; decimals: number }) {
  const rows = result.rows.slice(0, 20);
  const values = rows.map((r) => (typeof r.m0 === "number" ? r.m0 : 0));
  const max = Math.max(...values.map(Math.abs), 0);
  const total = typeof result.total?.m0 === "number" ? result.total.m0 : null;
  // "% of total" only means something when the total is the sum of the bars: not for an average,
  // lowest, highest or distinct count, and not when values of both signs cancel out. The sign check
  // covers every row (an "others" row and rows past the 20 drawn bars too), since the total does.
  const agg = result.spec?.measures[0]?.agg;
  const sameSign =
    total !== null &&
    result.rows.every((r) => typeof r.m0 !== "number" || r.m0 === 0 || Math.sign(r.m0) === Math.sign(total));
  const shareOf = (agg === "sum" || agg === "count") && total && sameSign ? total : null;
  if (!max) return null;
  return (
    <figure className="bar-chart" aria-label={`Bar chart: ${result.columns.find((c) => c.key === "m0")?.label}`}>
      {rows.map((row, i) => {
        const value = values[i];
        const share = shareOf ? ` · ${formatFixed((value / shareOf) * 100, 1)}% of total` : "";
        const label = String(row.g0 ?? "");
        return (
          <div className={`bar-row${row._kind === "others" ? " others" : ""}`} key={i} tabIndex={0}
            aria-label={`${label}: ${formatFixed(value, decimals)}${share}`}>
            <span className="bar-label" title={label}>
              {label}
            </span>
            <span className="bar-track">
              {/* At most 80% of the track, so the value label at the tip always fits. */}
              <span className={`bar${value < 0 ? " negative" : ""}`} style={{ width: `${(Math.abs(value) / max) * 80}%` }} />
              <span className="bar-value">{formatFixed(value, decimals)}</span>
            </span>
            <span className="bar-tip" role="tooltip">
              <strong>{label}</strong>
              {formatFixed(value, decimals)}
              {share}
            </span>
          </div>
        );
      })}
      {result.rows.length > rows.length ? <figcaption className="muted small">First 20 of {result.rows.length} shown; the table has all.</figcaption> : null}
    </figure>
  );
}
