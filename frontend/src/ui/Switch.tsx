import "./Switch.css";

type Props = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Accessible name when there is no visible label tied to it. */
  label?: string;
  /** Render only the track (the row around it is the switch, e.g. the menu's Dark mode row). */
  decorative?: boolean;
};

/** The violet on/off switch. */
export function Switch({ checked, onChange, label, decorative }: Props) {
  if (decorative) return <span className={`ui-switch${checked ? " is-on" : ""}`} aria-hidden="true" />;
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} className={`ui-switch${checked ? " is-on" : ""}`} onClick={() => onChange(!checked)} />
  );
}
