import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { initials, userAvatarUrl } from '../util.js';
import { GUIDES, guideBySlug } from '../appearance.js';

// /guides is a selector between the available docs; /guides/<slug> opens one of them same-origin in
// a full-bleed iframe (deep-linkable + browser-back friendly). Public — works before login.
const slugFromPath = () => {
  const p = window.location.pathname;
  return p.startsWith('/guides/') ? p.slice('/guides/'.length).replace(/\/+$/, '') : '';
};

export default function GuidesPage({ user, appearance, onHome, onLogout }) {
  const avatar = user ? userAvatarUrl(user) : null;
  const displayName = user ? (user.global_name || user.username) : null;

  const [active, setActive] = useState(() => guideBySlug(slugFromPath()));

  // If we landed on an unknown /guides/<slug>, normalise the URL back to the selector.
  useEffect(() => {
    if (!active && slugFromPath()) window.history.replaceState({}, '', '/guides');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the sub-view in sync with browser Back/Forward within the guides section.
  useEffect(() => {
    const onPop = () => setActive(guideBySlug(slugFromPath()));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const openGuide = (g) => {
    if (window.location.pathname !== `/guides/${g.slug}`) window.history.pushState({}, '', `/guides/${g.slug}`);
    setActive(g);
  };
  const backToSelector = () => {
    if (window.location.pathname !== '/guides') window.history.pushState({}, '', '/guides');
    setActive(null);
  };

  return (
    <div className="page guides-page">
      <div className="guides-bar">
        <div className="guides-nav">
          <button type="button" className="guides-back" onClick={onHome}>‹ Dashboard</button>
          {active && <button type="button" className="guides-back" onClick={backToSelector}>‹ Guides</button>}
        </div>
        <div className="guides-user">
          {user ? (
            <>
              {avatar ? (
                <img className="user-avatar" src={avatar} alt="" />
              ) : (
                <span className="user-avatar user-avatar--fallback">{initials(displayName)}</span>
              )}
              <span className="user-name">{displayName}</span>
              {onLogout && <button className="btn btn-ghost btn-sm" onClick={onLogout}>Log out</button>}
            </>
          ) : (
            <a className="btn btn-ghost btn-sm" href={api.loginUrl}>Log in</a>
          )}
        </div>
      </div>

      {active ? (
        <iframe title={active.title} src={active.url} className="guides-frame" />
      ) : (
        <div className="guides-select">
          <div className="gs-inner">
            <h1>Viobot guides</h1>
            <p className="gs-sub">Pick a guide to get started.</p>
            <div className="guide-cards">
              {GUIDES.map((g) => (
                <button key={g.slug} type="button" className="guide-card" onClick={() => openGuide(g)}>
                  <span className="gc-ic">{g.icon}</span>
                  <span className="gc-title">
                    {g.title}
                    {g.tag && <span className="gc-tag">{g.tag}</span>}
                  </span>
                  <p className="gc-blurb">{g.blurb}</p>
                  <span className="gc-go">Open →</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
