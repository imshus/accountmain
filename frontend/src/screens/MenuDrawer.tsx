import { useState } from "react";
import { logOut } from "../lock";
import { navigate, type Route } from "../router";
import { initialsOf, useSession } from "../session";
import { Avatar, Button, Drawer, Icon, IconButton, Sheet, type IconName } from "../ui";
import "./MenuDrawer.css";

export type MenuDrawerProps = {
  open: boolean;
  onClose: () => void;
};

type Row = {
  label: string;
  icon: IconName;
  tint: "violet" | "mint" | "rose" | "amber";
  go: Route | "subscription";
};

const ROWS: Row[] = [
  { label: "Masters", icon: "layers", tint: "violet", go: { name: "masters" } },
  { label: "Dashboard", icon: "grid", tint: "mint", go: { name: "dashboard" } },
  // The saved AI chats: Home and its tab always open a new chat, so this is the way back to an old one.
  { label: "History", icon: "clock", tint: "rose", go: { name: "history" } },
  { label: "Subscription", icon: "diamond", tint: "amber", go: "subscription" },
];

/** The side menu (menu.html): the company, Masters, Dashboard, History, Subscription and Logout. The server comes from
 * frontend/.env (VITE_API_URL), so there is no server field. */
export default function MenuDrawer({ open, onClose }: MenuDrawerProps) {
  const { company } = useSession();
  const [sheet, setSheet] = useState<"subscription" | "logout" | null>(null);

  const go = (target: Row["go"]) => {
    if (target === "subscription") {
      setSheet("subscription");
      return;
    }
    onClose();
    navigate(target);
  };

  return (
    <Drawer open={open} onClose={onClose} label="Menu">
      <IconButton icon="close" variant="close" label="Close menu" onClick={onClose} />

      <div className="menu-profile">
        <Avatar initials={initialsOf(company?.name)} size="lg" />
        <h2 title={company?.name}>{company?.name ?? "Accounts AI"}</h2>
        <p>
          <Icon name="diamond" size={11} stroke={2.4} />
          PREMIUM MEMBER
        </p>
      </div>

      <nav className="menu-settings" aria-label="Settings">
        {ROWS.map((row) => (
          <button key={row.label} type="button" onClick={() => go(row.go)}>
            <span className={`menu-ico menu-ico--${row.tint}`} aria-hidden="true">
              <Icon name={row.icon} size={15} />
            </span>
            <span className="menu-settings__label">{row.label}</span>
            <Icon name="right" size={14} className="menu-chev" />
          </button>
        ))}
      </nav>

      <Button variant="danger" size="lg" block icon="logout" className="menu-logout" onClick={() => setSheet("logout")}>
        Logout
      </Button>

      <Sheet
        open={sheet === "subscription"}
        onClose={() => setSheet(null)}
        title="Subscription"
        description="You're a Premium member: everything in Accounts.ai is included."
        actions={
          <Button variant="brand" onClick={() => setSheet(null)} data-autofocus>
            OK
          </Button>
        }
      >
        <ul className="menu-perks">
          <li>
            <Icon name="check" size={15} stroke={2.2} />
            AI answers on your Excel and books, with every figure checked
          </li>
          <li>
            <Icon name="check" size={15} stroke={2.2} />
            Sales, purchases, gold stock and GST returns
          </li>
          <li>
            <Icon name="check" size={15} stroke={2.2} />
            Your books and chats kept safe on your server
          </li>
        </ul>
      </Sheet>
      <Sheet
        open={sheet === "logout"}
        onClose={() => setSheet(null)}
        title="Log out?"
        description="Accounts.ai locks on this phone until you log in again. Your books and chats stay safe."
        actions={
          <>
            <Button onClick={() => setSheet(null)} data-autofocus>
              Cancel
            </Button>
            <Button
              variant="danger"
              icon="logout"
              onClick={() => {
                setSheet(null);
                onClose();
                logOut();
              }}
            >
              Logout
            </Button>
          </>
        }
      />
    </Drawer>
  );
}
