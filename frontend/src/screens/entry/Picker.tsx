import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useBackHandler } from "../../router";
import { Icon } from "../../ui";
import "./Picker.css";

export type PickerOption = { value: string; label: string; sub?: string };

type Props = {
  /** id of the button, for the field's <label htmlFor>. */
  id: string;
  value: string;
  options: PickerOption[];
  onSelect: (value: string) => void;
  placeholder: string;
  /** "Add new" was tapped; gets what was typed in the search box, if anything. */
  onAdd: (typed: string) => void;
  invalid?: boolean;
  describedBy?: string;
  loading?: boolean;
};

const SEARCH_FROM = 7; // longer lists get a search box

/** The design's open-in-place dropdown (Item: Bangle / Chain / Ring / + Add new), used for party, salesman and item. */
export function Picker({ id, value, options, onSelect, placeholder, onAdd, invalid, describedBy, loading }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const selected = options.find((o) => o.value === value);
  const q = query.trim().toLowerCase();
  const shown = q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options;

  const close = (refocus = true) => {
    setOpen(false);
    setQuery("");
    if (refocus) button.current?.focus();
  };
  useBackHandler(open, () => close());

  // A tap anywhere else closes the list, as a native select does.
  useEffect(() => {
    if (!open) return;
    const onDown = (event: PointerEvent) => {
      if (!wrap.current?.contains(event.target as Node)) close(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  const options$ = () => [...(list.current?.querySelectorAll<HTMLElement>("[role=option]") ?? [])];
  const focusOption = (index: number) => {
    const all = options$();
    if (all.length) all[Math.max(0, Math.min(all.length - 1, index))].focus();
  };

  const openList = (focus: "selected" | "none") => {
    setOpen(true);
    if (focus === "none") return;
    requestAnimationFrame(() => {
      const all = options$();
      const at = all.findIndex((el) => el.getAttribute("aria-selected") === "true");
      if (options.length >= SEARCH_FROM) wrap.current?.querySelector<HTMLInputElement>("input")?.focus();
      else focusOption(at < 0 ? 0 : at);
    });
  };

  const choose = (next: string) => {
    onSelect(next);
    close();
  };

  const onButtonKey = (event: KeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      openList("selected");
    }
  };

  const onListKey = (event: KeyboardEvent<HTMLUListElement>) => {
    const all = options$();
    const at = all.indexOf(document.activeElement as HTMLElement);
    const moves: Record<string, number> = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: all.length - 1 };
    if (event.key in moves) {
      event.preventDefault();
      focusOption(moves[event.key]);
    } else if ((event.key === "Enter" || event.key === " ") && at >= 0) {
      event.preventDefault();
      choose(shown[at].value);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
    }
  };

  return (
    <div
      ref={wrap}
      className="entry-picker"
      onBlur={(event) => {
        if (open && !wrap.current?.contains(event.relatedTarget as Node | null) && event.relatedTarget) close(false);
      }}
    >
      <button
        ref={button}
        id={id}
        type="button"
        className={`entry-picker__btn${open ? " is-open" : ""}${selected ? "" : " is-empty"}`}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        onClick={() => (open ? close() : openList("none"))}
        onKeyDown={onButtonKey}
      >
        <span className="entry-picker__value">{selected?.label ?? (loading ? "Loading…" : placeholder)}</span>
        <Icon name={open ? "up" : "down"} size={18} />
      </button>
      {open ? (
        <div className="entry-picker__panel">
          {options.length >= SEARCH_FROM ? (
            <div className="entry-picker__search">
              <Icon name="search" size={16} />
              <input
                className="entry-picker__query"
                type="search"
                value={query}
                placeholder="Search"
                aria-label="Search the list"
                enterKeyHint="search"
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    focusOption(0);
                  } else if (event.key === "Enter" && shown.length === 1) {
                    event.preventDefault();
                    choose(shown[0].value);
                  } else if (event.key === "Escape") {
                    event.preventDefault();
                    event.stopPropagation();
                    close();
                  }
                }}
              />
            </div>
          ) : null}
          <ul ref={list} className="entry-picker__list" role="listbox" aria-labelledby={id} onKeyDown={onListKey}>
            {shown.map((option) => (
              <li
                key={option.value}
                role="option"
                tabIndex={-1}
                aria-selected={option.value === value}
                className="entry-picker__opt"
                onClick={() => choose(option.value)}
              >
                <span>{option.label}</span>
                {option.sub ? <small>{option.sub}</small> : null}
              </li>
            ))}
            {!shown.length ? (
              <li className="entry-picker__none" role="presentation">
                {q ? `No “${query.trim()}” yet` : loading ? "Loading…" : "Nothing here yet"}
              </li>
            ) : null}
          </ul>
          <button
            type="button"
            className="entry-picker__add"
            onClick={() => {
              const typed = query.trim();
              // Focus back on the field first, so the Add sheet returns focus there when it closes.
              close();
              onAdd(typed);
            }}
          >
            <Icon name="addc" size={18} />
            {q ? `Add “${query.trim()}”` : "Add new"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
