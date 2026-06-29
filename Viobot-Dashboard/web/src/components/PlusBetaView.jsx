import { useEffect, useState } from 'react';
import { api } from '../api.js';
import AnnouncementsEditor from './AnnouncementsEditor.jsx';
import AvatarEditor from './AvatarEditor.jsx';

export default function PlusBetaView({ guildId }) {
  const [data, setData] = useState(undefined);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(undefined); setError(null);
    api.getPremium(guildId).then(setData).catch((e) => setError(String(e.message || e)));
  }, [guildId]);

  if (error) return <p className="notice error">Couldn't load access: {error}</p>;
  if (data === undefined) return <p className="muted">Loading access…</p>;

  return (
    <>
      <section className="config-card">
        <h3 className="config-group-title">Access</h3>
        <div className="config-fields">
          <div className="config-row">
            <div className="config-label">
              <span>Plus (Discord entitlement)</span>
              {!data.plusAvailable && <span className="config-help">entitlement check unavailable</span>}
            </div>
            <div className="config-value"><span className={`pill ${data.plus ? 'pill-on' : 'pill-off'}`}>{data.plus ? 'Active' : 'Not active'}</span></div>
          </div>
          <div className="config-row">
            <div className="config-label"><span>Beta program</span></div>
            <div className="config-value">
              <span className={`pill ${data.isBetaGuild ? 'pill-on' : 'pill-off'}`}>
                {data.isBetaGuild ? `Enabled · ${data.betaFeatureCount} feature(s)` : 'Off'}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="config-card">
        <h3 className="config-group-title">Feature access</h3>
        <div className="config-fields">
          {data.features.map((f) => (
            <div key={f.key} className="config-row">
              <div className="config-label"><span>{f.label}</span><span className="config-help mono">{f.key}</span></div>
              <div className="config-value">
                {f.allowed ? <span className="pill pill-on">{f.source}</span> : <span className="pill pill-off">Locked</span>}
              </div>
            </div>
          ))}
        </div>
      </section>

      <AvatarEditor guildId={guildId} />
      <AnnouncementsEditor guildId={guildId} />

      <p className="muted small config-note">
        Access (above) is controlled by Discord entitlements and the bot owner — read-only here.
        Custom contact categories are in the <b>Tickets</b> tab.
      </p>
    </>
  );
}
