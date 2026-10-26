import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import "./Tile.css";

type Props = {
  icon: IconName;
  label: ReactNode;
  /** Icon colour: mint (Sales), amber (Purchase), brand (Stock). */
  tone?: "mint" | "amber" | "brand";
  onClick: () => void;
};

/** A Home report tile: a 92px poster square with a coloured icon and the label under it. Put tiles in <TileRow>. */
export function Tile({ icon, label, tone = "brand", onClick }: Props) {
  return (
    <button type="button" className="ui-tile" onClick={onClick}>
      <span className={`ui-tile__art ui-tile__art--${tone}`}>
        <Icon name={icon} size={30} />
      </span>
      {label}
    </button>
  );
}

/** Tiles side by side; scrolls sideways when they do not fit. */
export function TileRow({ children }: { children: ReactNode }) {
  return <div className="ui-tiles">{children}</div>;
}
