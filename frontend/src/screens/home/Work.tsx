import { useState, type ReactNode } from "react";
import { AnalysisView } from "../../components/AnalysePanel";
import DataTable from "../../components/DataTable";
import { formatCount } from "../../format";
import type { AnalysisResult, AnalysisSpec, ChatResult, FormulaCheck, QueryResult } from "../../types";
import { Badge, Button } from "../../ui";
import { workLines } from "./chatUtils";
import "./Work.css";

/** One expandable piece of work. Its body is only built while open (analyses draw charts and tables). */
function Item({ title, tag, children }: { title: ReactNode; tag?: ReactNode; children: () => ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="chat-work__item" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        <span className="chat-work__title">{title}</span>
        {tag}
      </summary>
      {open ? <div className="chat-work__body">{children()}</div> : null}
    </details>
  );
}

function AnalysisItem({ analysis, onOpen }: { analysis: AnalysisResult; onOpen?: (spec: AnalysisSpec) => void }) {
  return (
    <Item title={analysis.description || "Analysis"} tag={analysis.error ? <Badge tone="rose">error</Badge> : null}>
      {() =>
        analysis.error ? (
          <p className="chat-work__error">{analysis.error}</p>
        ) : (
          <>
            <AnalysisView result={analysis} compact />
            {onOpen ? (
              <Button size="sm" variant="soft" onClick={() => onOpen(analysis.spec)}>
                Open in Analyse
              </Button>
            ) : null}
          </>
        )
      }
    </Item>
  );
}

function QueryItem({ query, index }: { query: QueryResult; index: number }) {
  return (
    <Item
      title={`Query ${index + 1}`}
      tag={query.error ? <Badge tone="rose">error</Badge> : <span className="chat-work__meta">{formatCount(query.row_count)} row{query.row_count === 1 ? "" : "s"}</span>}
    >
      {() => (
        <>
          <pre className="chat-work__sql">{query.sql}</pre>
          {query.error ? <p className="chat-work__error">{query.error}</p> : <DataTable columns={query.columns} rows={(query.rows ?? []).slice(0, 50)} />}
        </>
      )}
    </Item>
  );
}

/** A formula checked on every row (also used by a file's Calculator). */
export function FormulaDetails({ check }: { check: FormulaCheck }) {
  const all = check.matches !== undefined && check.matches === check.rows_checked;
  return (
    <Item
      title={`Formula check: ${check.target} = ${check.expression}`}
      tag={
        check.error ? (
          <Badge tone="rose">error</Badge>
        ) : (
          <Badge tone={all ? "mint" : "amber"}>
            {formatCount(check.matches ?? 0)}/{formatCount(check.rows_checked ?? 0)} rows
          </Badge>
        )
      }
    >
      {() =>
        check.error ? (
          <p className="chat-work__error">{check.error}</p>
        ) : (
          <>
            <p className="chat-work__note">
              Tolerance {check.tolerance}; largest difference {check.max_difference ?? "—"}
              {check.rows_blank ? `; ${check.rows_blank} rows had no value to check` : ""}.
            </p>
            {check.examples && check.examples.length > 0 ? (
              <DataTable columns={["Entry", "Actual", "Formula gives", "Difference"]} rows={check.examples.map((e) => [e.row, e.actual, e.expected, e.difference])} />
            ) : null}
          </>
        )
      }
    </Item>
  );
}

/**
 * "how this was calculated": the steps in a line each (as the design's gold box), then every analysis, query,
 * formula check and calculation with its numbers.
 */
export function Work({ result, steps, onOpenAnalysis }: { result: ChatResult; steps?: string[]; onOpenAnalysis?: (spec: AnalysisSpec) => void }) {
  return (
    <div className="chat-work">
      <ul className="chat-work__lines">
        {workLines(result, steps).map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
      {(result.analyses ?? []).map((analysis, index) => (
        <AnalysisItem key={`a${index}`} analysis={analysis} onOpen={onOpenAnalysis} />
      ))}
      {result.queries.map((query, index) => (
        <QueryItem key={`q${index}`} query={query} index={index} />
      ))}
      {(result.formula_checks ?? []).map((check, index) => (
        <FormulaDetails key={`f${index}`} check={check} />
      ))}
      {result.calculations?.length ? (
        <Item title="Calculations" tag={<span className="chat-work__meta">{result.calculations.length}</span>}>
          {() => (
            <ul className="chat-work__calcs">
              {result.calculations.map((c, index) => (
                <li key={index}>
                  <code>{c.expression}</code> = {c.error ? <span className="chat-work__error">{c.error}</span> : <strong>{c.result}</strong>}
                </li>
              ))}
            </ul>
          )}
        </Item>
      ) : null}
    </div>
  );
}
