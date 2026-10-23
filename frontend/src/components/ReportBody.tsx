import { memo, type ReactNode } from "react";
import { formatValue } from "../format";
import type { Report } from "../types";
import ChecksList from "./ChecksList";
import ReportTableView, { downloadCsv } from "./ReportTableView";

type Props = {
  report: Report;
  renderGroup?: (row: Record<string, unknown>) => ReactNode;
  children?: ReactNode;
};

/** Title, summary cards, checks and tables of any report (single sheet or sales + purchases). */
function ReportBody({ report, renderGroup, children }: Props) {
  return (
    <div className="report">
      <div className="report-head">
        <h3>{report.title}</h3>
      </div>
      {report.cards.length ? (
        <div className="cards">
          {report.cards.map((c) => {
            const text = formatValue(c.value, c.format);
            return (
              <div className="card stat" key={c.label}>
                <span className="stat-label">{c.label}</span>
                <span className={`stat-value${text.startsWith("-") && c.format !== "drcr" && c.format !== "weight_drcr" ? " negative" : ""}`}>{text}</span>
                {c.hint ? <span className="pill success small-pill">{c.hint}</span> : null}
              </div>
            );
          })}
        </div>
      ) : null}
      <ChecksList checks={report.checks} title="Checks" />
      {report.tables.map((t, i) => (
        <div key={i} className="report-section">
          <div className="report-head">
            {t.title ? <h4>{t.title}</h4> : <span />}
            {t.rows.length ? (
              <button className="button small-button" onClick={() => void downloadCsv(t, `${report.title}${t.title ? ` - ${t.title}` : ""}.csv`)}>
                Download CSV
              </button>
            ) : null}
          </div>
          <ReportTableView table={t} renderGroup={renderGroup} />
        </div>
      ))}
      {children}
    </div>
  );
}

// Memoised so that editing a report's parameters does not redraw the report on screen.
export default memo(ReportBody);
