import { useEffect, useState } from 'react';
import { api } from './api.js';
import Login from './pages/Login.jsx';
import GuildPicker from './pages/GuildPicker.jsx';

export default function App() {
  const [user, setUser] = useState(undefined); // undefined = loading, null = logged out

  useEffect(() => {
    api.me().then((d) => setUser(d?.user ?? null)).catch(() => setUser(null));
  }, []);

  if (user === undefined) {
    return <div className="center muted">Loading…</div>;
  }
  if (!user) {
    return <Login />;
  }
  return <GuildPicker user={user} onLogout={() => api.logout().then(() => setUser(null))} />;
}
