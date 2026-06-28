import { useEffect, useState } from 'react';
import { api } from '../api.js';

function initials(name) {
  return (name || '?')
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export default function GuildPicker({ user, onLogout }) {
  const [data, setData] = useState(undefined);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.guilds().then(setData).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">Viobot Dashboard</div>
        <div className="user">
          <span className="muted">{user.global_name || user.username}</span>
          <button className="btn btn-ghost" onClick={onLogout}>Log out</button>
        </div>
      </header>

      <main className="container">
        <h2>Select a server</h2>
        <p className="muted">
          Servers where Viobot is present and you have administrator permissions.
        </p>

        {error && <p className="notice error">Couldn't load servers: {error}</p>}
        {data === undefined && !error && <p className="muted">Loading servers…</p>}

        {data && (
          <>
            {data.guilds.length === 0 ? (
              <div className="empty">
                <p>No servers to configure yet.</p>
                <p className="muted small">
                  You administer {data.counts.admin} server(s); Viobot is in {data.counts.botPresent}.
                  None overlap — add Viobot to a server you administer.
                </p>
              </div>
            ) : (
              <div className="guild-grid">
                {data.guilds.map((g) => (
                  // Phase 2 turns this into a link to the per-server config page.
                  <button key={g.id} className="guild-card" title={`Configure ${g.name}`}>
                    <span className="guild-avatar">{initials(g.name)}</span>
                    <span className="guild-name">{g.name}</span>
                    {g.owner && <span className="badge">Owner</span>}
                  </button>
                ))}
              </div>
            )}
            <p className="muted small">
              {data.counts.accessible} configurable · {data.counts.admin} administered · {data.counts.botPresent} with Viobot
            </p>
          </>
        )}
      </main>
    </div>
  );
}
