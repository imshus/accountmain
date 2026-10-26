import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import "./Button.css";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /**
   * primary: the design's big ink button (Save sale) · brand: violet fill · soft: violet tint (Connect) ·
   * danger: rose outline (Logout) · ghost: text only · plain: raised surface with a border
   */
  variant?: "primary" | "brand" | "soft" | "danger" | "ghost" | "plain";
  size?: "sm" | "md" | "lg";
  block?: boolean;
  icon?: IconName;
  busy?: boolean;
};

/** A text button. Defaults to type="button". */
export function Button({ variant = "plain", size = "md", block, icon, busy, className, children, type = "button", disabled, ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={`ui-btn ui-btn--${variant} ui-btn--${size}${block ? " ui-btn--block" : ""}${className ? ` ${className}` : ""}`}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy ? <span className="ui-btn__spin" aria-hidden="true" /> : icon ? <Icon name={icon} size={size === "sm" ? 15 : 17} /> : null}
      {children}
    </button>
  );
}

type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  icon: IconName;
  /** Accessible name (required: the button shows only an icon). */
  label: string;
  /**
   * bare: the header's 44px transparent button · round: the composer's 44px grey circle ·
   * accent: round with a violet icon (mic) · open: round, violet tint (an open + menu) · send: violet fill
   */
  variant?: "bare" | "round" | "accent" | "open" | "send" | "close";
  /** A small rose dot (unread notifications). */
  dot?: boolean;
  size?: number;
};

/** A 44px icon-only button. */
export function IconButton({ icon, label, variant = "bare", dot, size, className, type = "button", ...rest }: IconButtonProps) {
  return (
    <button type={type} className={`ui-iconbtn ui-iconbtn--${variant}${className ? ` ${className}` : ""}`} aria-label={label} title={label} {...rest}>
      <Icon name={icon} size={size ?? (variant === "bare" ? 24 : variant === "close" ? 17 : 20)} stroke={variant === "bare" ? 1.8 : undefined} />
      {dot ? <span className="ui-iconbtn__dot" aria-hidden="true" /> : null}
    </button>
  );
}

/** Bits of text inside a button that should not wrap. */
export function Nowrap({ children }: { children: ReactNode }) {
  return <span className="ui-nowrap">{children}</span>;
}
