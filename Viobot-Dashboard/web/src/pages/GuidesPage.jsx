import { api } from '../api.js';
import { initials, userAvatarUrl } from '../util.js';
import { guidesUrl, guidesLabel } from '../appearance.js';

// Embeds the docs site (own origin) full-bleed. Instead of the full dashboard top bar (which would
// double up with the docs' own header), a slim cosmic strip flows into the docs header below it.
// Public — works before login; shows a Log in action when logged out.
export default function GuidesPage({ user, appearance, onHome, onLogout }) {
  const avatar = user ? userAvatarUrl(user) : null;
  const displayName = user ? (user.global_name || user.username) : null;

  return (
    <div className="page guides-page">
      <div className="guides-bar">
        <button type="button" className="guides-back" onClick={onHome}>‹ Dashboard</button>
        <div className="guides-user">
          {user ? (
            <>
              {avatar ? (
                <img className="user-avatar" src={avatar} alt="" />
              ) : (
                <span className="user-avatar user-avatar--fallback">{initials(displayName)}</span>
              )}
              <span className="user-name">{displayName}</span>
              <button className="btn btn-ghost btn-sm" onClick={onLogout}>Log out</button>
            </>
          ) : (
            <a className="btn btn-ghost btn-sm" href={api.loginUrl}>Log in</a>
          )}
        </div>
      </div>
      <iframe title={guidesLabel(appearance)} src={guidesUrl(appearance)} className="guides-frame" />
    </div>
  );
}
