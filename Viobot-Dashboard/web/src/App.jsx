import { useEffect, useState } from 'react';
import { api } from './api.js';
import { applyAppearance } from './appearance.js';
import Login from './pages/Login.jsx';
import GuildPicker from './pages/GuildPicker.jsx';
import ConfigPage from './pages/ConfigPage.jsx';
import AdminPage from './pages/AdminPage.jsx';
import GuidesPage from './pages/GuidesPage.jsx';

const isGuidesPath = () => window.location.pathname === '/guides' || window.location.pathname.startsWith('/guides/');

export default function App() {
  const [user, setUser] = useState(undefined); // undefined = loading, null = logged out
  const [isAdmin, setIsAdmin] = useState(false);
  const [appearance, setAppearance] = useState({});
  const [selectedGuild, setSelectedGuild] = useState(null);
  const [showAdmin, setShowAdmin] = useState(false);
  const [route, setRoute] = useState(() => (isGuidesPath() ? 'guides' : 'app')); // lightweight router-less routing

  useEffect(() => {
    api.getAppearance().then((d) => { applyAppearance(d.appearance || {}); setAppearance(d.appearance || {}); }).catch(() => {});
    api.me().then((d) => { setUser(d?.user ?? null); setIsAdmin(Boolean(d?.isAdmin)); }).catch(() => setUser(null));
  }, []);

  // Keep the view in sync with the browser Back/Forward buttons.
  useEffect(() => {
    const onPop = () => setRoute(isGuidesPath() ? 'guides' : 'app');
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const onAppearanceChange = (a) => { applyAppearance(a); setAppearance(a); };

  const goGuides = () => { if (!isGuidesPath()) window.history.pushState({}, '', '/guides'); setRoute('guides'); };
  const goApp = () => { if (isGuidesPath()) window.history.pushState({}, '', '/'); setRoute('app'); };

  if (user === undefined) return <div className="center muted">Loading…</div>;

  const logout = () => api.logout().then(() => { setSelectedGuild(null); setShowAdmin(false); setUser(null); setIsAdmin(false); });

  // Guides is public — reachable before login and from every page.
  if (route === 'guides') {
    return (
      <GuidesPage
        user={user}
        appearance={appearance}
        onHome={goApp}
        onLogout={user ? logout : undefined}
      />
    );
  }

  if (!user) return <Login appearance={appearance} />;

  if (selectedGuild) {
    return (
      <ConfigPage
        user={user}
        guild={selectedGuild}
        appearance={appearance}
        isAdmin={isAdmin}
        onBack={() => setSelectedGuild(null)}
        onGuides={goGuides}
        onLogout={logout}
      />
    );
  }
  if (showAdmin && isAdmin) {
    return (
      <AdminPage
        user={user}
        appearance={appearance}
        onAppearanceChange={onAppearanceChange}
        onBack={() => setShowAdmin(false)}
        onGuides={goGuides}
        onLogout={logout}
      />
    );
  }
  return (
    <GuildPicker
      user={user}
      isAdmin={isAdmin}
      appearance={appearance}
      onSelect={setSelectedGuild}
      onAdmin={() => setShowAdmin(true)}
      onGuides={goGuides}
      onLogout={logout}
    />
  );
}
