import type { RefObject } from "react";
import { Icon, IconButton } from "../../../ui";
import "./txn.css";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
  inputRef: RefObject<HTMLInputElement | null>;
  busy?: boolean;
};

/** The search box the header's search button opens: party, invoice number, salesman. */
export function TxnSearch({ value, onChange, onClose, inputRef, busy }: Props) {
  return (
    <div className="txn-search" role="search">
      <span className="txn-search__icon" aria-hidden="true">
        <Icon name="search" size={18} />
      </span>
      {/* ui-input's look (Field.css); a plain input so the ref reaches it */}
      <input
        ref={inputRef}
        type="search"
        className="ui-input txn-search__input"
        placeholder="Party, invoice no. or salesman"
        aria-label="Search entries"
        value={value}
        enterKeyHint="search"
        autoComplete="off"
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            onClose();
          }
        }}
        aria-busy={busy || undefined}
      />
      <IconButton icon="close" label="Close search" variant="close" className="txn-search__close" onClick={onClose} />
    </div>
  );
}
