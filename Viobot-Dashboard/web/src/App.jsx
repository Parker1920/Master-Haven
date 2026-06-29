import { useEffect, useState } from 'react';
import { api } from './api.js';
import { applyAppearance } from './appearance.js';
import Login from './pages/Login.jsx';
import GuildPicker from './pages/GuildPicker.jsx';
import ConfigPage from './pages/ConfigPage.jsx';
import AdminPage from './pages/AdminPage.jsx';

export default function App() {
  const [user, setUser] = useState(undefined); // undefined = loading, null = logged out
  const [isAdmin, setIsAdmin] = useState(false);
  const [appearance, setAppearance] = useState({});
  const [selectedGuild, setSelectedGuild] = useState(null);
  const [showAdmin, setShowAdmin] = useState(false);

  useEffect(() => {
    api.getAppearance().then((d) => { applyAppearance(d.appearance || {}); setAppearance(d.appearance || {}); }).catch(() => {});
    api.me().then((d) => { setUser(d?.user ?? null); setIsAdmin(Boolean(d?.isAdmin)); }).catch(() => setUser(null));
  }, []);

  const onAppearanceChange = (a) => { applyAppearance(a); setAppearance(a); };

  if (user === undefined) return <div className="center muted">Loading…</div>;
  if (!user) return <Login appearance={appearance} />;

  const logout = () => api.logout().then(() => { setSelectedGuild(null); setShowAdmin(false); setUser(null); });

  if (selectedGuild) {
    return <ConfigPage user={user} guild={selectedGuild} appearance={appearance} onBack={() => setSelectedGuild(null)} onLogout={logout} />;
  }
  if (showAdmin && isAdmin) {
    return <AdminPage user={user} appearance={appearance} onAppearanceChange={onAppearanceChange} onBack={() => setShowAdmin(false)} onLogout={logout} />;
  }
  return (
    <GuildPicker
      user={user}
      isAdmin={isAdmin}
      appearance={appearance}
      onSelect={setSelectedGuild}
      onAdmin={() => setShowAdmin(true)}
      onLogout={logout}
    />
  );
}
