import type { HTMLAttributes, ReactNode } from "react";
import "./Card.css";

type CardProps = Omit<HTMLAttributes<HTMLElement>, "title"> & {
  /** A heading at the top (17px display, as "Weight & rates"). */
  title?: ReactNode;
  as?: "section" | "div" | "article";
};

/** The design's big form card: 28px corners, raised surface, large soft shadow, 20px padding, 14px gaps. */
export function Card({ title, as: Tag = "section", className, children, ...rest }: CardProps) {
  return (
    <Tag className={`ui-card${className ? ` ${className}` : ""}`} {...rest}>
      {title ? <h2 className="ui-card__title">{title}</h2> : null}
      {children}
    </Tag>
  );
}

type BoxProps = HTMLAttributes<HTMLElement> & {
  /** hero: the big summary box (Total fine stock) · warn: rose border (a karat with negative stock) */
  variant?: "plain" | "hero" | "warn";
  as?: "section" | "div" | "article" | "li";
  children: ReactNode;
};

/** A smaller panel: 14px corners, raised surface, hairline border (Stock's karat rows, list rows). */
export function Box({ variant = "plain", as: Tag = "article", className, children, ...rest }: BoxProps) {
  return (
    <Tag className={`ui-box ui-box--${variant}${className ? ` ${className}` : ""}`} {...rest}>
      {children}
    </Tag>
  );
}

/** A small uppercase label ("DATE", "MONEY", "SERVER"). */
export function Overline({ children, as: Tag = "span", id }: { children: ReactNode; as?: "span" | "h2" | "h3" | "p" | "label"; id?: string }) {
  return (
    <Tag className="ui-overline" id={id}>
      {children}
    </Tag>
  );
}

/** A section heading inside a screen ("Reports", "By karat"). */
export function SectionTitle({ children, as: Tag = "h2", id }: { children: ReactNode; as?: "h2" | "h3"; id?: string }) {
  return (
    <Tag className="ui-section-title" id={id}>
      {children}
    </Tag>
  );
}
