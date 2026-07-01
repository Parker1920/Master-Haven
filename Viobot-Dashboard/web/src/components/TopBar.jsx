import { api } from '../api.js';
import { initials, userAvatarUrl } from '../util.js';
import { brandName, guidesUrl, guidesLabel, guidesEnabled } from '../appearance.js';

// Shared app header used by every page. Left slot is either a `back` button (config/admin pages)
// or the brand (optionally clickable via `onHome`). Right cluster: Guides → ⚙ Admin → user → Log out.
// `user` may be null (e.g. the public Guides view before login) — then a Log in action is shown.
export default function TopBar({ appearance, user, isAdmin, back, onHome, onGuides, onAdmin, onLogout, guidesActive }) {
  const showGuides = guidesEnabled(appearance) && guidesUrl(appearance) && typeof onGuides === 'function';
  const avatar = user ? userAvatarUrl(user) : null;
  const displayName = user ? (user.global_name || user.username) : null;

  const brand = (
    <>
      {appearance?.logo ? <img className="brand-logo" src={appearance.logo} alt="" /> : <span className="brand-dot" />}
      {brandName(appearance)}
    </>
  );

  return (
    <header className="topbar">
      {back ? (
        <div className="brand"><button className="back-btn" onClick={back.onClick}>{back.label}</button></div>
      ) : onHome ? (
        <button type="button" className="brand brand-home" onClick={onHome}>{brand}</button>
      ) : (
        <div className="brand">{brand}</div>
      )}

      <div className="user">
        {showGuides && (
          <button className={`btn btn-ghost ${guidesActive ? 'is-active' : ''}`} onClick={onGuides}>
            {guidesLabel(appearance)}
          </button>
        )}
        {isAdmin && onAdmin && <button className="btn btn-ghost" onClick={onAdmin}>⚙ Admin</button>}
        {user ? (
          <>
            {avatar ? (
              <img className="user-avatar" src={avatar} alt="" />
            ) : (
              <span className="user-avatar user-avatar--fallback">{initials(displayName)}</span>
            )}
            <span className="user-name">{displayName}</span>
            <button className="btn btn-ghost" onClick={onLogout}>Log out</button>
          </>
        ) : (
          <a className="btn btn-ghost" href={api.loginUrl}>Log in</a>
        )}
      </div>
    </header>
  );
}
