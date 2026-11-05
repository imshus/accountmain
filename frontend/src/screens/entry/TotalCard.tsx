import { formatPaise } from "../../format";
import { Card } from "../../ui";
import type { Preview } from "./calc";
import { grams, money } from "./money";

const carats = (mct: number) => `${(mct / 1000).toFixed(3)} ct`;

/** The design's Total card: the bill's weights and amounts over all its items ("—" until there is one). */
export function TotalCard({ figures: f }: { figures: Preview }) {
  const rows: [string, string | null][] = [
    ["Total Gross Weight", f.grossMg ? grams(f.grossMg) : null],
    ["Total Net Weight", f.netMg ? grams(f.netMg) : null],
    ["Total Fine Weight", f.fineMg ? grams(f.fineMg) : null],
    ["Total Diamond Weight", f.diaMct ? carats(f.diaMct) : null],
    ["Total Diamond Value", f.diamond ? money(f.diamond) : null],
    ...(f.stone ? ([["Total Stone Value", money(f.stone)]] as [string, string][]) : []),
    ["Total Labour Amount", f.labour ? money(f.labour) : null],
    ["Total Amount", f.total ? formatPaise(f.total, 0) : null],
  ];
  return (
    <Card title="Total">
      <dl className="entry-totals">
        {rows.map(([label, value]) => (
          <div key={label} className={label === "Total Amount" ? "is-grand" : undefined}>
            <dt>{label}</dt>
            <dd>{value ?? "—"}</dd>
          </div>
        ))}
      </dl>
      {f.roundOff ? <p className="entry-note">Total includes round off {formatPaise(f.roundOff, 2, true)}</p> : null}
    </Card>
  );
}
