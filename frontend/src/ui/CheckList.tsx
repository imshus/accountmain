import { Icon } from "./icons";
import "./CheckList.css";

export type CheckItem = { level: "ok" | "info" | "warning" | "error"; message: string };

/** The design's check lines under a report (green tick = passed, grey info, rose alert). Takes a report's `checks`. */
export function CheckList({ items }: { items: CheckItem[] }) {
  if (!items.length) return null;
  return (
    <ul className="ui-checks">
      {items.map((item, i) => (
        <li key={i} className={`ui-checks__item ui-checks__item--${item.level}`}>
          <Icon name={item.level === "ok" ? "check" : item.level === "info" ? "info" : "alert"} size={14} stroke={2.2} />
          <span>{item.message}</span>
        </li>
      ))}
    </ul>
  );
}
