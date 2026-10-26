import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Icon } from "./icons";
import "./Field.css";

type FieldProps = {
  label: ReactNode;
  /** id of the control inside, so the label is tied to it. Use useId() in the screen. */
  htmlFor?: string;
  /** Grey help line under the control. */
  hint?: ReactNode;
  /** Rose error line under the control. */
  error?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** A labelled form row: OVERLINE label, the control, an optional hint or error. */
export function Field({ label, htmlFor, hint, error, children, className }: FieldProps) {
  return (
    <div className={`ui-field${className ? ` ${className}` : ""}`}>
      {htmlFor ? (
        <label className="ui-overline" htmlFor={htmlFor}>
          {label}
        </label>
      ) : (
        <span className="ui-overline">{label}</span>
      )}
      {children}
      {error ? (
        <p className="ui-field__error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="ui-field__hint">{hint}</p>
      ) : null}
    </div>
  );
}

/** Two fields side by side (Gross / Net weight). */
export function FieldRow({ children }: { children: ReactNode }) {
  return <div className="ui-fieldrow">{children}</div>;
}

/** The design's text input (16px semibold, so phones do not zoom). For amounts use inputMode="decimal". */
export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`ui-input${className ? ` ${className}` : ""}`} {...rest} />;
}

export function TextArea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`ui-input ui-textarea${className ? ` ${className}` : ""}`} {...rest} />;
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  /** A gold tag inside the box, e.g. the karat "22K" next to the purity. */
  tag?: ReactNode;
};

/** A native select in the design's style (chevron on the right). */
export function Select({ className, tag, children, ...rest }: SelectProps) {
  return (
    <div className="ui-select-wrap">
      <select className={`ui-input ui-select${className ? ` ${className}` : ""}`} {...rest}>
        {children}
      </select>
      {tag ? <span className="ui-select__tag">{tag}</span> : null}
    </div>
  );
}

/** A worked-out value (dashed box): Fine weight 10.534 g · "net wt × purity %". */
export function AutoValue({ value, note, tone }: { value: ReactNode; note?: ReactNode; tone?: "gold" | "mint" | "rose" }) {
  return (
    <output className="ui-auto">
      <strong className={tone ? `ui-auto--${tone}` : undefined}>{value}</strong>
      {note ? <small>{note}</small> : null}
    </output>
  );
}

/** "2026-10-24" -> "24/10/2026" */
export function toDMY(iso: string): string {
  const [y, m, d] = iso.split("-");
  return y && m && d ? `${d}/${m}/${y}` : iso;
}

type DateProps = {
  /** YYYY-MM-DD */
  value: string;
  onChange: (value: string) => void;
  label?: string;
  min?: string;
  max?: string;
};

/** The violet date chip (24/10/2026). Tapping it opens the device's date picker. */
export function DatePill({ value, onChange, label = "Date", min, max }: DateProps) {
  const id = useId();
  return (
    <span className="ui-datepill">
      <Icon name="cal" size={14} stroke={2.2} />
      <span aria-hidden="true">{toDMY(value)}</span>
      <input
        id={id}
        className="ui-datepill__input"
        type="date"
        value={value}
        min={min}
        max={max}
        aria-label={label}
        onChange={(event) => event.target.value && onChange(event.target.value)}
      />
    </span>
  );
}
