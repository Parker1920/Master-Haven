import { useEffect, useState } from 'react';
import { api } from '../api.js';
import Footer from '../components/Footer.jsx';

export default function Login() {
  const [health, setHealth] = useState(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);

  const oauthReady = health?.oauthConfigured;

  return (
    <div className="auth-page">
      <div className="auth-main">
        <div className="card">
          <h1>Viobot Dashboard</h1>
          <p className="muted">Manage Viobot's settings for the servers you administer.</p>

          {oauthReady ? (
            <a className="btn btn-discord" href={api.loginUrl}>Log in with Discord</a>
          ) : (
            <>
              <button className="btn btn-discord" disabled>Log in with Discord</button>
              <p className="notice">
                Discord login isn't configured yet. Add <code>DISCORD_CLIENT_ID</code> /{' '}
                <code>DISCORD_CLIENT_SECRET</code> (from art3mis) to <code>server/.env</code>.
              </p>
            </>
          )}

          {health?.devLogin && (
            <p className="notice">
              <a className="btn btn-ghost" href={api.devLoginUrl}>Dev login (testing)</a>
              <br />Internal testing bypass — no Discord login. Disabled in production.
            </p>
          )}

          {health?.db && (
            <p className="muted small">
              {health.db.error
                ? `DB: ${health.db.error}`
                : `Connected to Viobot DB · ${health.db.registeredGuilds} registered server(s).`}
            </p>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
}
