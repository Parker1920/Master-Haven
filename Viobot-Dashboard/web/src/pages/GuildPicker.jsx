import { useEffect, useState } from 'react';
import { api } from '../api.js';
import Footer from '../components/Footer.jsx';
import { initials, guildIconUrl, userAvatarUrl, fallbackGradient } from '../util.js';

function GuildAvatar({ guild }) {
  const [broken, setBroken] = useState(false);
  const url = guildIconUrl(guild);
  if (url && !broken) {
    return <img className="guild-avatar" src={url} alt="" loading="lazy" onError={() => setBroken(true)} />;
  }
  return (
    <span className="guild-avatar guild-avatar--fallback" style={{ background: fallbackGradient(guild.name) }}>
      {initials(guild.name)}
    </span>
  );
}

export default function GuildPicker({ user, onSelect, onLogout }) {
  const [data, setData] = useState(undefined);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.guilds().then(setData).catch((e) => setError(String(e)));
  }, []);

  const avatar = userAvatarUrl(user);
  const displayName = user.global_name || user.username;

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="brand-dot" />
          Viobot Dashboard
        </div>
        <div className="user">
          {avatar ? (
            <img className="user-avatar" src={avatar} alt="" />
          ) : (
            <span className="user-avatar user-avatar--fallback">{initials(displayName)}</span>
          )}
          <span className="user-name">{displayName}</span>
          <button className="btn btn-ghost" onClick={onLogout}>Log out</button>
        </div>
      </header>

      <main className="container">
        <div className="page-head">
          <h2>Select a server</h2>
          <p className="muted">Servers where Viobot is present and you have administrator permissions.</p>
        </div>

        {error && <p className="notice error">Couldn't load servers: {error}</p>}

        {data === undefined && !error && (
          <div className="guild-grid">
            {[0, 1, 2, 3].map((i) => <div key={i} className="guild-card guild-card--skeleton" />)}
          </div>
        )}

        {data && (
          data.guilds.length === 0 ? (
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
                <button key={g.id} className="guild-card" title={`Configure ${g.name}`} onClick={() => onSelect(g)}>
                  <GuildAvatar guild={g} />
                  <span className="guild-meta">
                    <span className="guild-name">{g.name}</span>
                    <span className={`role-badge ${g.owner ? 'role-owner' : 'role-admin'}`}>
                      {g.owner ? '👑 Owner' : 'Admin'}
                    </span>
                  </span>
                  <span className="guild-go" aria-hidden="true">›</span>
                </button>
              ))}
            </div>
          )
        )}
      </main>
      <Footer />
    </div>
  );
}
