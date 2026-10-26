import "./Avatar.css";

type Props = {
  /** Two letters, e.g. initialsOf(company.name). */
  initials: string;
  size?: "sm" | "lg";
  /** Makes it a button (the header avatar opens the menu). */
  onClick?: () => void;
  /** Button label, e.g. "Open menu". */
  label?: string;
  expanded?: boolean;
};

/** The company avatar: brand gradient square with initials (header: framed 32px; menu: 64px). */
export function Avatar({ initials, size = "sm", onClick, label, expanded }: Props) {
  const face = <span className={`ui-avatar__face ui-avatar__face--${size}`}>{initials}</span>;
  if (!onClick) return <span className={`ui-avatar ui-avatar--${size}`}>{face}</span>;
  return (
    <button type="button" className={`ui-avatar ui-avatar--${size}`} onClick={onClick} aria-label={label} aria-expanded={expanded}>
      {face}
    </button>
  );
}
