import { useState } from "react";
import type { VoucherRow } from "../../../types";
import { addDays, utcDay, voucherRupees } from "../figures";
import { registerTotals } from "../register/RegisterParts";
import "./reports.css";

/** A total in paise as the design writes it: ₹24,960, −₹3,100. */
export const rupees = (paise: number) => voucherRupees(paise, paise < 0 ? "−" : "");

export type SpendDay = { date: string; paise: number };

/** The 7 days ending today, each with its purchases (returns taken off, as on the Purchase screen). */
export function weekOf(bills: VoucherRow[], today: string): SpendDay[] {
  return Array.from({ length: 7 }, (_, i) => {
    const date = addDays(today, i - 6);
    return { date, paise: registerTotals(bills.filter((v) => v.date === date)).paise };
  });
}

const weekday = new Intl.DateTimeFormat("en-GB", { weekday: "short", timeZone: "UTC" });
const dayMonth = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
/** "Mon 26 Oct". */
const dayName = (date: string) => `${weekday.format(utcDay(date))} ${dayMonth.format(utcDay(date))}`;

/** "Weekly spend" (the owner's picture): a bar per day, as tall as that day's purchases. Tapping a bar shows its day and
 * amount above the bars; tapping it again (or Escape) goes back to the 7 days' total. */
export function WeeklySpend({ days }: { days: SpendDay[] }) {
  const [picked, setPicked] = useState<string | null>(null);
  const top = Math.max(0, ...days.map((d) => d.paise));
  const day = days.find((d) => d.date === picked);
  const total = days.reduce((sum, d) => sum + d.paise, 0);
  return (
    <section className="rep-week" aria-labelledby="rep-week-title">
      <h2 id="rep-week-title" className="rep-week__title">
        Weekly spend
      </h2>
      <p className="rep-week__readout" aria-live="polite">
        <span>{day ? dayName(day.date) : "Last 7 days"}</span>
        <strong>{rupees(day ? day.paise : total)}</strong>
      </p>
      <div
        className={`rep-week__bars${day ? " has-pick" : ""}`}
        role="group"
        aria-labelledby="rep-week-title"
        onKeyDown={(e) => {
          if (e.key === "Escape" && day) {
            e.preventDefault();
            setPicked(null);
          }
        }}
      >
        {days.map((d) => (
          <button
            key={d.date}
            type="button"
            className={`rep-bar${d === day ? " is-picked" : ""}`}
            aria-label={`${dayName(d.date)}: ${rupees(d.paise)}`}
            aria-pressed={d === day}
            onClick={() => setPicked(d === day ? null : d.date)}
          >
            <span className="rep-bar__track">
              {/* A day with nothing bought keeps a short stub. */}
              <span
                className={`rep-bar__fill${d.paise > 0 ? "" : " is-zero"}`}
                style={d.paise > 0 && top > 0 ? { height: `${(d.paise / top) * 100}%` } : undefined}
              />
            </span>
            <span className="rep-bar__day" aria-hidden="true">
              {weekday.format(utcDay(d.date)).charAt(0)}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
