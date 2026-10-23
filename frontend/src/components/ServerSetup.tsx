import { useState } from "react";
import { checkServer, saveServer, serverUrl } from "../api";

type Props = {
  /** Why the screen is showing (e.g. the saved server stopped answering). */
  problem?: string | null;
  onCancel?: () => void;
};

/** The app keeps its books on your computer: tell it where the Accounts.ai backend runs. */
export default function ServerSetup({ problem, onCancel }: Props) {
  const [url, setUrl] = useState(serverUrl());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await checkServer(url);
      saveServer(url);
      window.location.reload();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <section className="panel narrow-panel">
      <h1>Connect to your server</h1>
      <p className="muted">
        Your books stay on your computer. On that computer, run <code>backend\start-server.bat</code>; it shows the address to type
        here. The phone must be on the same Wi-Fi (or the server must be reachable over the internet).
      </p>
      {problem ? <div className="callout warning">{problem}</div> : null}
      <form className="stack-form" onSubmit={(e) => void connect(e)}>
        <label className="field">
          <span>Server address</span>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://192.168.1.10:8000" inputMode="url"
            autoCapitalize="off" autoCorrect="off" spellCheck={false} required />
        </label>
        {error ? <div className="callout warning">{error}</div> : null}
        <div className="sql-actions">
          <button className="button primary" type="submit" disabled={busy || !url.trim()}>
            {busy ? "Checking…" : "Connect"}
          </button>
          {onCancel ? (
            <button className="button" type="button" onClick={onCancel}>
              Cancel
            </button>
          ) : null}
        </div>
      </form>
    </section>
  );
}
