import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { BooksProvider } from "./books";
import ErrorBoundary from "./components/ErrorBoundary";
import { LibraryProvider } from "./library";
import { useLoggedOut } from "./lock";
import { hrefOf, navigate, useRoute, useScrollRestoration, type Route } from "./router";
import { useRouteFocus } from "./routeFocus";
import HomeScreen from "./screens/HomeScreen";
import LoggedOutScreen from "./screens/LoggedOutScreen";
import { NotificationsSheet } from "./screens/books/BellScope";
import { useBookWarnings } from "./screens/books/useBookWarnings";
import MenuDrawer from "./screens/MenuDrawer";
import { initialsOf, SessionProvider, useSession } from "./session";
import { ScreenLoading, ShellContext, type ShellActions } from "./ui";
import "./App.css";

// Home (with the chat) is in the main bundle; every other screen loads on its own, and is fetched in the
// background once Home is up so opening it is still instant.
const loaders = {
  HistoryScreen: () => import("./screens/HistoryScreen"),
  EntryScreen: () => import("./screens/EntryScreen"),
  RegisterScreen: () => import("./screens/RegisterScreen"),
  StockScreen: () => import("./screens/StockScreen"),
  TransactionsScreen: () => import("./screens/TransactionsScreen"),
  ReportsScreen: () => import("./screens/ReportsScreen"),
  MastersScreen: () => import("./screens/legacy/MastersScreen"),
  DashboardScreen: () => import("./screens/legacy/DashboardScreen"),
  OfflineScreen: () => import("./screens/OfflineScreen"),
  MetalScreen: () => import("./screens/legacy/MetalScreen"),
  NewCompanyScreen: () => import("./screens/legacy/NewCompanyScreen"),
};
const HistoryScreen = lazy(loaders.HistoryScreen);
const EntryScreen = lazy(loaders.EntryScreen);
const RegisterScreen = lazy(loaders.RegisterScreen);
const StockScreen = lazy(loaders.StockScreen);
const TransactionsScreen = lazy(loaders.TransactionsScreen);
const ReportsScreen = lazy(loaders.ReportsScreen);
const MastersScreen = lazy(loaders.MastersScreen);
const DashboardScreen = lazy(loaders.DashboardScreen);
const OfflineScreen = lazy(loaders.OfflineScreen);
const MetalScreen = lazy(loaders.MetalScreen);
const NewCompanyScreen = lazy(loaders.NewCompanyScreen);

export default function App() {
  return (
    <SessionProvider>
      <LibraryProvider>
        <BooksProvider>
          <Shell />
        </BooksProvider>
      </LibraryProvider>
    </SessionProvider>
  );
}

/** Every screen except Home, by route. */
function screenFor(route: Route): ReactNode {
  switch (route.name) {
    case "home":
      return null;
    case "history":
      return <HistoryScreen />;
    case "entry":
      return <EntryScreen kind={route.kind} />;
    case "register":
      return <RegisterScreen kind={route.kind} />;
    case "stock":
      return <StockScreen metal={route.metal ?? "gold"} />;
    case "transactions":
      return <TransactionsScreen search={route.search ?? false} />;
    case "reports":
      return <ReportsScreen />;
    case "masters":
      return <MastersScreen />;
    case "dashboard":
      return <DashboardScreen tab={route.tab} />;
    case "metal":
      return <MetalScreen kind={route.kind} />;
    case "new-company":
      return <NewCompanyScreen />;
  }
}

function Shell() {
  const route = useRoute();
  const session = useSession();
  const loggedOut = useLoggedOut();
  const [menuOpen, setMenuOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  // Home stays mounted once opened (hidden on other screens), so an answer being written keeps arriving.
  const [homeSeen, setHomeSeen] = useState(route.name === "home");
  // The same bell on every screen: the books' warnings (negative stock, books out of balance, no AI key).
  const { warnings } = useBookWarnings();
  useScrollRestoration();
  useRouteFocus(route);

  useEffect(() => {
    setMenuOpen(false);
    if (route.name === "home") setHomeSeen(true);
  }, [route]);

  useEffect(() => {
    const prefetch = window.setTimeout(() => Object.values(loaders).forEach((load) => void load().catch(() => null)), 2000);
    return () => window.clearTimeout(prefetch);
  }, []);

  const openMenu = useCallback(() => setMenuOpen(true), []);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const shell = useMemo<ShellActions>(
    () => ({
      initials: initialsOf(session.company?.name),
      openMenu,
      menuOpen,
      onBell: () => setBellOpen(true),
      onSearch: () => navigate({ name: "transactions", search: true }),
      bellDot: warnings.length > 0,
    }),
    [session.company?.name, warnings.length, openMenu, menuOpen],
  );

  // Logged out from the menu: the app stays locked on this device until "Log in".
  if (loggedOut) return <LoggedOutScreen />;
  // The server is not answering (or the build has no VITE_API_URL): only "try again" makes sense.
  if (session.status === "no-server" || session.status === "offline") {
    return (
      <Suspense fallback={<ScreenLoading />}>
        <OfflineScreen />
      </Suspense>
    );
  }
  if (!session.company) return <ScreenLoading label="Connecting…" />;

  const isHome = route.name === "home";
  return (
    <ShellContext.Provider value={shell}>
      <div className="app-screens" inert={menuOpen}>
        {homeSeen ? (
          <div hidden={!isHome}>
            <ErrorBoundary>
              <HomeScreen chatId={route.name === "home" ? route.chat : undefined} active={isHome} />
            </ErrorBoundary>
          </div>
        ) : null}
        {!isHome ? (
          <ErrorBoundary key={hrefOf(route)}>
            <Suspense fallback={<ScreenLoading />}>{screenFor(route)}</Suspense>
          </ErrorBoundary>
        ) : null}
      </div>
      <MenuDrawer open={menuOpen} onClose={closeMenu} />
      <NotificationsSheet open={bellOpen} onClose={() => setBellOpen(false)} warnings={warnings} />
    </ShellContext.Provider>
  );
}
