import { useMemo, type ReactNode } from "react";
import { navigate } from "../../router";
import { useSession } from "../../session";
import { Button, Notice, Sheet, ShellContext, useShell } from "../../ui";
import type { BookWarning } from "./useBookWarnings";
import "./books.css";

/** The bell's sheet: the books' warnings, each with a way to the screen that fixes it. */
export function NotificationsSheet({ open, onClose, warnings }: { open: boolean; onClose: () => void; warnings: BookWarning[] }) {
  const { aiLabel } = useSession();
  const go = (warning: BookWarning) => {
    onClose();
    if (warning.action) navigate(warning.action.to);
  };
  return (
    <Sheet open={open} onClose={onClose} title="Notifications" description={warnings.length ? `${warnings.length} thing${warnings.length === 1 ? "" : "s"} to check in your books.` : undefined}>
      <div className="bell-list">
        {warnings.map((w) => (
          <Notice
            key={w.id}
            tone={w.level === "error" ? "error" : "warning"}
            action={
              w.action ? (
                <Button size="sm" variant="soft" onClick={() => go(w)}>
                  {w.action.label}
                </Button>
              ) : undefined
            }
          >
            {w.message}
          </Notice>
        ))}
        {warnings.length === 0 ? <Notice tone="success">All clear: no warnings in your books.</Notice> : null}
        {aiLabel ? <p className="bell-foot">Connected · AI: {aiLabel}</p> : null}
      </div>
    </Sheet>
  );
}

/** Wraps a tab screen whose header search button does something of its own (Transactions: open its search box). */
export function BellScope({ children, onSearch }: { children: ReactNode; onSearch?: () => void }) {
  const shell = useShell();
  const value = useMemo(() => ({ ...shell, onSearch: onSearch ?? shell.onSearch }), [shell, onSearch]);
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}
