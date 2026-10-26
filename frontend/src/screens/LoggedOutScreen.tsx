import { logIn } from "../lock";
import { Button, Glow } from "../ui";
import "./legacy/legacy.css";

/** After the menu's Logout: the app stays locked on this device until "Log in". Books and chats are untouched. */
export default function LoggedOutScreen() {
  return (
    <div className="server-screen">
      <Glow />
      <div className="server-screen__col">
        <div className="server-screen__brand" aria-hidden="true">
          A
        </div>
        <h1 className="server-screen__title">You're logged out</h1>
        <p className="server-screen__lead">Your books and chats are safe. Log in to continue.</p>
        <Button variant="primary" size="lg" block onClick={logIn} data-autofocus>
          Log in
        </Button>
      </div>
    </div>
  );
}
