import { Icon, type IconName } from "./icons";
import "./Segmented.css";

export type SegmentOption<T extends string> = {
  value: T;
  label: string;
  icon?: IconName;
  /** Colour of the icon when selected (Sale mint, Purchase amber). */
  tone?: "mint" | "amber" | "brand";
};

type Props<T extends string> = {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  /** block: the full-width Sale / Purchase switch · metal: the small gold Gold / Silver pill switch */
  variant?: "block" | "metal";
};

/** Pick one of a few options. */
export function Segmented<T extends string>({ options, value, onChange, label, variant = "block" }: Props<T>) {
  return (
    <div className={`ui-seg ui-seg--${variant}`} role="group" aria-label={label} style={{ ["--seg-n" as string]: options.length }}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`ui-seg__opt${option.tone ? ` ui-seg__opt--${option.tone}` : ""}`}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.icon ? <Icon name={option.icon} size={16} stroke={2.2} /> : null}
          {option.label}
        </button>
      ))}
    </div>
  );
}
