import { useEffect, useState } from 'react';
import { api } from './api.js';
import Login from './pages/Login.jsx';
import GuildPicker from './pages/GuildPicker.jsx';
import ConfigPage from './pages/ConfigPage.jsx';

export default function App() {
  const [user, setUser] = useState(undefined); // undefined = loading, null = logged out
  const [selectedGuild, setSelectedGuild] = useState(null);

  useEffect(() => {
    api.me().then((d) => setUser(d?.user ?? null)).catch(() => setUser(null));
  }, []);

  if (user === undefined) return <div className="center muted">Loading…</div>;
  if (!user) return <Login />;

  const logout = () => api.logout().then(() => { setSelectedGuild(null); setUser(null); });

  if (selectedGuild) {
    return (
      <ConfigPage
        user={user}
        guild={selectedGuild}
        onBack={() => setSelectedGuild(null)}
        onLogout={logout}
      />
    );
  }
  return <GuildPicker user={user} onSelect={setSelectedGuild} onLogout={logout} />;
}
