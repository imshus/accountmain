import { useMemo, useState } from "react";
import { api } from "../api";
import { formatBytes, formatCount, formatTimestamp } from "../format";
import type { AnalysisSpec, DatasetDetail, Health, Sheet } from "../types";
import AnalysePanel from "./AnalysePanel";
import CalculatorPanel from "./CalculatorPanel";
import ChatPanel, { suggestions } from "./ChatPanel";
import ChecksList from "./ChecksList";
import ColumnStats from "./ColumnStats";
import DataTable from "./DataTable";
import EntriesPanel from "./EntriesPanel";
import ReportsPanel from "./ReportsPanel";
import SummaryCards from "./SummaryCards";
import SummaryTableView from "./SummaryTableView";

type Props = {
  dataset: DatasetDetail;
  health: Health | null;
  onDatasetChange: (dataset: DatasetDetail) => void;
};

const VIEWS = [
  ["overview", "Overview"],
  ["analyse", "Analyse"],
  ["chat", "Ask AI"],
  ["reports", "Reports"],
  ["entries", "Entries"],
  ["calculator", "Calculator"],
] as const;
type View = (typeof VIEWS)[number][0];

export default function DatasetView({ dataset, health, onDatasetChange }: Props) {
  const [sheetIndex, setSheetIndex] = useState(0);
  const [view, setView] = useState<View>("overview");
  // Analyse stays mounted once opened so its choices survive tab switches; the AI can open it with a request.
  const [analyse, setAnalyse] = useState<{ key: number; spec: AnalysisSpec | null } | null>(null);
  const openAnalyse = (spec: AnalysisSpec | null) => {
    setAnalyse((current) => ({ key: (current?.key ?? 0) + (spec ? 1 : 0), spec: spec ?? current?.spec ?? null }));
    setView("analyse");
  };
  const sheet = dataset.sheets[Math.min(sheetIndex, dataset.sheets.length - 1)];
  const { profile } = sheet;
  const totalRows = dataset.sheets.reduce((sum, s) => sum + s.row_count, 0);
  const category = profile.summary.by_category;
  // Reference-number columns (invoice no, HSN, mobile…) by name and label, so the preview shows them ungrouped.
  const identifiers = useMemo(
    () => new Set(profile.columns.filter((c) => c.role === "identifier").flatMap((c) => [c.name, c.label])),
    [profile.columns],
  );

  function replaceSheet(updated: Sheet) {
    onDatasetChange({ ...dataset, sheets: dataset.sheets.map((s) => (s.table_name === updated.table_name ? updated : s)) });
  }

  return (
    <div className="dataset-view">
      <header className="dataset-header">
        <div>
          <h1 title={dataset.filename}>{dataset.filename}</h1>
          <p className="muted small">
            Uploaded {formatTimestamp(dataset.uploaded_at)} · {formatBytes(dataset.size_bytes)} ·{" "}
            {dataset.sheets.length} sheet{dataset.sheets.length === 1 ? "" : "s"} · {formatCount(totalRows)} rows
          </p>
        </div>
      </header>

      {dataset.sheets.length > 1 ? (
        <nav className="tabs" aria-label="Sheets">
          {dataset.sheets.map((s, index) => (
            <button
              key={s.table_name}
              className={`tab${index === sheetIndex ? " active" : ""}`}
              onClick={() => setSheetIndex(index)}
              aria-current={index === sheetIndex ? "page" : undefined}
            >
              {s.sheet_name}
              <span className="tab-count">{formatCount(s.row_count)}</span>
            </button>
          ))}
        </nav>
      ) : null}

      <nav className="view-tabs segmented" aria-label="Views">
        {VIEWS.map(([key, label]) => (
          <button key={key} className={view === key ? "active" : ""} onClick={() => (key === "analyse" ? openAnalyse(null) : setView(key))} aria-current={view === key ? "page" : undefined}>
            {label}
          </button>
        ))}
      </nav>

      {/* The chat stays mounted so the conversation survives switching views. */}
      {analyse ? (
        <div hidden={view !== "analyse"}>
          <AnalysePanel key={analyse.key} initialSpec={analyse.spec} loadTables={() => api.datasetFields(dataset.id)}
            run={(spec) => api.analyseDataset(dataset.id, spec)} />
        </div>
      ) : null}

      <div hidden={view !== "chat"}>
        <ChatPanel
          onOpenAnalysis={openAnalyse}
          scope={`ds-${dataset.id}`}
          stream={(messages, provider, onEvent, options) => api.chatStream(dataset.id, messages, provider, onEvent, options)}
          subject={dataset.filename}
          tables={dataset.sheets}
          defaultTable={sheet.table_name}
          suggestionList={suggestions(sheet)}
          health={health}
          runSql={(sql) => api.runSql(dataset.id, sql)}
        />
      </div>

      {view === "overview" ? (
        <>
          <ChecksList checks={profile.checks ?? []} title="Data checks" />
          <SummaryCards profile={profile} />
          {profile.summary.monthly || category ? (
            <div className="grid-2">
              {profile.summary.monthly ? (
                <section className="panel">
                  <h2>Month by month</h2>
                  <SummaryTableView table={profile.summary.monthly} />
                </section>
              ) : null}
              {category ? (
                <section className="panel">
                  <h2>
                    {category.rows.length < category.groups ? `Top ${category.rows.length} of ${formatCount(category.groups)} by ` : "By "}
                    {category.columns[0]?.label ?? category.category_column}
                  </h2>
                  <SummaryTableView table={category} />
                </section>
              ) : null}
            </div>
          ) : null}
          <NotesForAi key={sheet.table_name} datasetId={dataset.id} sheet={sheet} onSaved={replaceSheet} />
          <section className="panel">
            <h2>Columns</h2>
            <ColumnStats columns={profile.columns} rowCount={profile.row_count} preview={sheet.preview} />
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Data preview</h2>
              <span className="muted small">
                First {formatCount(sheet.preview.rows.length)} of {formatCount(sheet.row_count)} rows · SQL table <code>{sheet.table_name}</code>
              </span>
            </div>
            <DataTable columns={sheet.preview.columns} rows={sheet.preview.rows} identifiers={identifiers} />
          </section>
        </>
      ) : null}
      {view === "reports" ? <ReportsPanel key={sheet.table_name} dataset={dataset} sheet={sheet} /> : null}
      {view === "entries" ? <EntriesPanel key={sheet.table_name} dataset={dataset} sheet={sheet} onSheetChanged={replaceSheet} /> : null}
      {view === "calculator" ? <CalculatorPanel key={sheet.table_name} dataset={dataset} sheet={sheet} onSheetChanged={replaceSheet} /> : null}
    </div>
  );
}

function NotesForAi({ datasetId, sheet, onSaved }: { datasetId: number; sheet: Sheet; onSaved: (sheet: Sheet) => void }) {
  const [notes, setNotes] = useState(sheet.profile.user_notes ?? "");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const dirty = notes !== (sheet.profile.user_notes ?? "");

  async function save() {
    setState("saving");
    try {
      onSaved(await api.saveNotes(datasetId, sheet.table_name, notes));
      setState("saved");
    } catch {
      setState("error");
    }
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Notes for the AI</h2>
        <span className="muted small">Explain columns, codes or rules so answers use the right meaning.</span>
      </div>
      <textarea
        rows={3}
        value={notes}
        onChange={(e) => {
          setNotes(e.target.value);
          setState("idle");
        }}
        placeholder={'e.g. "Credit = sales receipts. Tunch is purity in %. Wt/Rs = Wt means metal is settled by weight."'}
        maxLength={5000}
        aria-label="Notes for the AI"
      />
      <div className="sql-actions">
        <button className="button primary small-button" onClick={() => void save()} disabled={!dirty || state === "saving"}>
          {state === "saving" ? "Saving…" : "Save notes"}
        </button>
        {state === "saved" && !dirty ? <span className="muted small">Saved. The AI reads these notes with every question.</span> : null}
        {state === "error" ? <span className="error-text small">Could not save the notes.</span> : null}
      </div>
    </section>
  );
}
