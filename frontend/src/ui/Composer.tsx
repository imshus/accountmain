import { useEffect, useLayoutEffect, useRef, type ClipboardEvent, type ReactNode, type Ref } from "react";
import { IconButton } from "./Button";
import { useBackHandler } from "../router";
import "./Composer.css";

type Props = {
  value: string;
  onChange: (value: string) => void;
  /** Enter (without Shift) or the send button. Not called while `busy`. */
  onSubmit: () => void;
  placeholder?: string;
  /** Accessible name of the text box. */
  label?: string;
  disabled?: boolean;
  /** An answer is being written: the right button becomes Stop (when onStop is given). */
  busy?: boolean;
  onStop?: () => void;
  /** Voice input. The mic shows while the box is empty; without onMic an empty box shows a disabled send button. */
  onMic?: () => void;
  listening?: boolean;
  /** The + button and its menu (e.g. <Menu> with Click / Upload). Leave out onMenuToggle to hide the + button. */
  menuOpen?: boolean;
  onMenuToggle?: (open: boolean) => void;
  menu?: ReactNode;
  /** Shown inside the box above the text row: attached file chips, a notice. */
  above?: ReactNode;
  onPaste?: (event: ClipboardEvent<HTMLTextAreaElement>) => void;
  inputRef?: Ref<HTMLTextAreaElement>;
  /** Grow up to this many pixels before scrolling. */
  maxHeight?: number;
};

/**
 * The floating ask box: + (attach menu), the text, and mic / send / stop. Put it in <AppShell composer={...}>, which
 * docks it above the tab bar. The text box grows with its text.
 */
export function Composer({
  value,
  onChange,
  onSubmit,
  placeholder = "Ask about a bill, invoice, or amount…",
  label = "Ask a question",
  disabled,
  busy,
  onStop,
  onMic,
  listening,
  menuOpen = false,
  onMenuToggle,
  menu,
  above,
  onPaste,
  inputRef,
  maxHeight = 140,
}: Props) {
  const box = useRef<HTMLTextAreaElement | null>(null);
  const closeMenu = useRef(() => onMenuToggle?.(false));
  closeMenu.current = () => onMenuToggle?.(false);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, [value, maxHeight]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && closeMenu.current();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);
  useBackHandler(menuOpen, () => closeMenu.current());

  const empty = !value.trim();
  const setRef = (el: HTMLTextAreaElement | null) => {
    box.current = el;
    if (typeof inputRef === "function") inputRef(el);
    else if (inputRef) inputRef.current = el;
  };

  return (
    <div className={`ui-composer${menuOpen ? " is-menu-open" : ""}`}>
      {menuOpen && menu ? (
        <>
          <div className="ui-composer__backdrop" onClick={() => onMenuToggle?.(false)} aria-hidden="true" />
          <div className="ui-composer__menu">{menu}</div>
        </>
      ) : null}
      <form
        className="ui-composer__box"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy && !empty && !disabled) onSubmit();
        }}
      >
        {above ? <div className="ui-composer__above">{above}</div> : null}
        <div className="ui-composer__row">
          {onMenuToggle ? (
            <IconButton
              icon={menuOpen ? "close" : "plus"}
              variant={menuOpen ? "open" : "round"}
              label={menuOpen ? "Close attach menu" : "Attach a photo or file"}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              onClick={() => onMenuToggle(!menuOpen)}
              disabled={disabled}
            />
          ) : null}
          <textarea
            ref={setRef}
            className="ui-composer__input"
            rows={1}
            value={value}
            placeholder={placeholder}
            aria-label={label}
            disabled={disabled}
            enterKeyHint="send"
            onChange={(event) => onChange(event.target.value)}
            onPaste={onPaste}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                if (!busy && !empty && !disabled) onSubmit();
              }
            }}
          />
          {busy && onStop ? (
            <IconButton icon="stop" variant="send" label="Stop" onClick={onStop} />
          ) : empty && onMic ? (
            <IconButton icon="mic" variant={listening ? "open" : "accent"} label={listening ? "Stop listening" : "Voice input"} aria-pressed={listening} onClick={onMic} disabled={disabled} />
          ) : (
            <IconButton icon="send" variant="send" label="Send" type="submit" disabled={disabled || busy || empty} />
          )}
        </div>
      </form>
    </div>
  );
}
