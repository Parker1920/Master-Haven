/**
 * Top-level App shell.
 *
 * Renders:
 *   - desktop nav (≥769px) with search + notification bell OR mobile top bar + bottom nav (<769px)
 *   - the routed page via #route-outlet
 *   - the toast overlay, and the DevPanel only in Vite dev mode
 */

import { useState } from "react";
import { Toast } from "./components/Toast";
import { DevPanel } from "./components/DevPanel";
import { Drawer } from "./components/Drawer";
import { SearchBar } from "./components/SearchBar";
import { NotificationBell } from "./components/NotificationBell";
import { useAuth } from "./hooks/useAuth";
import { useRoute } from "./router";
import { Civs } from "./pages/Civs";
import { CivPage } from "./pages/CivPage";
import { Compose } from "./pages/Compose";
import { Dashboard } from "./pages/Dashboard";
import { Draft } from "./pages/Draft";
import { Drafts } from "./pages/Drafts";
import { Inquisitions } from "./pages/Inquisitions";
import { InquisitionPage } from "./pages/InquisitionPage";
import { Login } from "./pages/Login";
import { Newsroom } from "./pages/Newsroom";
import { Profile } from "./pages/Profile";
import { Story } from "./pages/Story";
import { Timeline } from "./pages/Timeline";
import { Admin } from "./pages/Admin";
import { Avatar } from "./components/Avatar";

const PAGE_TITLES: Record<string, string> = {
  home: "Newsroom",
  civs: "Civilizations",
  civ: "Civilization",
  inquisitions: "Inquisitions",
  inquisition: "Inquisition",
  beat: "Newsroom",
  story: "Story",
  profile: "Profile",
  timeline: "Master timeline",
  dashboard: "Dashboard",
  drafts: "Drafts",
  draft: "Draft",
  compose: "New draft",
  admin: "Admin",
  notfound: "Not found",
};

export function App() {
  const route = useRoute();
  const { user } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="ta-app">
      {/* Desktop nav */}
      <nav className="ta-nav-desktop">
        <a href="#/" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="ta-logo-mark">TA</span>
          <span className="ta-logo-text">Travelers Archive</span>
        </a>
        <div className="ta-nav-spacer" />
        <SearchBar />
        <NavLink to="/" active={route.name === "home" || route.name === "beat"}>Newsroom</NavLink>
        <NavLink to="/civs" active={route.name === "civs" || route.name === "civ"}>Civilizations</NavLink>
        <NavLink to="/inquisitions" active={route.name === "inquisitions" || route.name === "inquisition"}>Inquisitions</NavLink>
        <NavLink to="/timeline" active={route.name === "timeline"}>Timeline</NavLink>
        <NavLink to="/dashboard" active={route.name === "dashboard"}>Dashboard</NavLink>
        <NavLink to="/drafts" active={route.name === "drafts" || route.name === "draft" || route.name === "compose"}>Drafts</NavLink>
        {user?.is_admin && (
          <NavLink to="/admin" active={route.name === "admin"}>Admin</NavLink>
        )}
        <NotificationBell />
        {user ? (
          <a href={`#/profile/${user.discord_username}`} className="ta-user-pill">
            <Avatar author={user} />
            <span>{user.display_name}</span>
          </a>
        ) : (
          <a href="#/login" className="ta-btn ta-btn-primary" style={{ padding: "5px 14px" }}>
            Sign in
          </a>
        )}
      </nav>

      {/* Mobile top bar */}
      <header className="ta-mobile-bar">
        <div className="ta-mobile-bar-left">
          <button className="ta-mobile-icon-btn" onClick={() => setDrawerOpen(true)} aria-label="Menu">≡</button>
          <span className="ta-logo-mark">TA</span>
          <span className="ta-mobile-page-title">{PAGE_TITLES[route.name] || "Travelers Archive"}</span>
        </div>
        <div className="ta-mobile-bar-right">
          <NotificationBell />
          {user ? (
            <a href={`#/profile/${user.discord_username}`}>
              <Avatar author={user} />
            </a>
          ) : (
            <a href="#/login" style={{ fontSize: 12, color: "var(--ta-accent-blue)", padding: "0 6px" }}>
              Sign in
            </a>
          )}
        </div>
      </header>

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      {/* Routed page */}
      <main id="route-outlet">
        <PageFor route={route} />
      </main>

      {/* Bottom nav (mobile only) */}
      <nav className="ta-bottom-nav">
        <div className="ta-bottom-nav-grid">
          <BottomNavLink to="/" label="News" active={route.name === "home" || route.name === "beat"} />
          <BottomNavLink to="/civs" label="Civs" active={route.name === "civs" || route.name === "civ"} />
          <BottomNavLink to="/inquisitions" label="Inq." active={route.name === "inquisitions" || route.name === "inquisition"} />
          <BottomNavLink to="/timeline" label="Time" active={route.name === "timeline"} />
          <BottomNavLink to="/drafts" label="Drafts" active={route.name === "drafts" || route.name === "draft" || route.name === "compose"} />
          <BottomNavLink to="/dashboard" label="Me" active={route.name === "dashboard"} />
        </div>
      </nav>

      <Toast />
      {import.meta.env.DEV && <DevPanel />}
    </div>
  );
}

function NavLink({ to, active, children }: { to: string; active: boolean; children: React.ReactNode }) {
  return <a href={"#" + to} className={`ta-nav-link${active ? " active" : ""}`}>{children}</a>;
}

function BottomNavLink({ to, label, active }: { to: string; label: string; active: boolean }) {
  return (
    <a href={"#" + to} className={`ta-bottom-nav-item${active ? " active" : ""}`}>{label}</a>
  );
}

function PageFor({ route }: { route: ReturnType<typeof useRoute> }) {
  switch (route.name) {
    case "home": return <Newsroom />;
    case "beat": return <Newsroom beat={route.slug} />;
    case "civs": return <Civs />;
    case "civ": return <CivPage slug={route.slug} />;
    case "inquisitions": return <Inquisitions />;
    case "inquisition": return <InquisitionPage id={route.id} />;
    case "story": return <Story id={route.id} />;
    case "profile": return <Profile slug={route.slug} />;
    case "timeline": return <Timeline />;
    case "dashboard": return <Dashboard />;
    case "drafts": return <Drafts />;
    case "draft": return <Draft id={route.id} />;
    case "compose": return <Compose doctype={route.doctype} />;
    case "login": return <Login />;
    case "admin": return <Admin />;
    case "notfound":
    default:
      return (
        <div className="ta-notfound">
          <div className="ta-notfound-code">404</div>
          <div className="ta-notfound-eyebrow">Off the map</div>
          <h2 className="ta-notfound-title">This page doesn't exist</h2>
          <p className="ta-notfound-body">
            The page you were looking for has been redacted, moved, or never existed in this reality.
          </p>
          <div className="ta-notfound-actions">
            <a href="#/" className="ta-btn ta-btn-primary">Back to newsroom</a>
            <a href="#/civs" className="ta-btn">Browse civilizations</a>
          </div>
        </div>
      );
  }
}
