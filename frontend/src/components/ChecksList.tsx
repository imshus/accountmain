import type { Check } from "../types";

const ICON = { ok: "✓", info: "i", warning: "!" } as const;

/** Data checks from importing a file or from a report: warnings first, then confirmations, then notes. */
export default function ChecksList({ checks, title }: { checks: Check[]; title?: string }) {
  if (checks.length === 0) return null;
  const order = { warning: 0, ok: 1, info: 2 } as const;
  const sorted = [...checks].sort((a, b) => order[a.level] - order[b.level]);
  const warnings = checks.filter((c) => c.level === "warning").length;
  return (
    <section className="checks" aria-label={title ?? "Data checks"}>
      {title ? (
        <h3 className="checks-title">
          {title}
          {warnings ? <span className="pill warning small-pill">{warnings} to review</span> : <span className="pill success small-pill">all clear</span>}
        </h3>
      ) : null}
      <ul>
        {sorted.map((check, index) => (
          <li key={index} className={`check check-${check.level}`}>
            <span className="check-icon" aria-hidden="true">
              {ICON[check.level]}
            </span>
            <span>{check.message}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
