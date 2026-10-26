import { useSession } from "../session";
import { Button, Glow, Notice } from "../ui";
import "./legacy/legacy.css";

/** Shown when the backend does not answer, or the app was built without VITE_API_URL. The address comes only from
 * frontend/.env, so the only thing to do here is try again. */
export default function OfflineScreen() {
  const session = useSession();
  const missing = session.status === "no-server";

  return (
    <div className="server-screen">
      <Glow />
      <div className="server-screen__col">
        <div className="server-screen__brand" aria-hidden="true">
          A
        </div>
        <h1 className="server-screen__title">{missing ? "No server in this build" : "Can't reach the server"}</h1>
        {missing ? (
          <p className="server-screen__lead">
            This app was built without a server address. Set <code>VITE_API_URL</code> in <code>frontend/.env</code> to an address that
            starts with https:// (or http:// for a PC on your network) and build it again.
          </p>
        ) : (
          <>
            <p className="server-screen__lead">
              Check that this device can reach the server (for a PC on your network, be on the same Wi-Fi), then try again. The server may
              also be restarting.
            </p>
            {session.error ? <Notice tone="warning">{session.error}</Notice> : null}
            <Button variant="primary" size="lg" block onClick={session.retry}>
              Try again
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
