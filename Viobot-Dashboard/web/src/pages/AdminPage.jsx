import { useState } from 'react';
import Footer from '../components/Footer.jsx';
import RegistryEditor from '../components/RegistryEditor.jsx';
import AppearanceEditor from '../components/AppearanceEditor.jsx';
import AdminsEditor from '../components/AdminsEditor.jsx';
import BotControl from '../components/BotControl.jsx';
import LogViewer from '../components/LogViewer.jsx';
import { initials, userAvatarUrl } from '../util.js';

export default function AdminPage({ user, appearance, onAppearanceChange, onBack, onLogout }) {
  const [tab, setTab] = useState('fields');
  const avatar = userAvatarUrl(user);
  const displayName = user.global_name || user.username;

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand"><button className="back-btn" onClick={onBack}>‹ Servers</button></div>
        <div className="user">
          {avatar ? <img className="user-avatar" src={avatar} alt="" /> : <span className="user-avatar user-avatar--fallback">{initials(displayName)}</span>}
          <span className="user-name">{displayName}</span>
          <button className="btn btn-ghost" onClick={onLogout}>Log out</button>
        </div>
      </header>

      <main className="container">
        <div className="config-head">
          <div>
            <h2>Dashboard admin</h2>
            <p className="muted small">Manage the config options and who can administer the dashboard</p>
          </div>
        </div>

        <div className="config-tabs">
          <button className={`config-tab ${tab === 'fields' ? 'active' : ''}`} onClick={() => setTab('fields')}>Config fields</button>
          <button className={`config-tab ${tab === 'appearance' ? 'active' : ''}`} onClick={() => setTab('appearance')}>Appearance</button>
          <button className={`config-tab ${tab === 'bot' ? 'active' : ''}`} onClick={() => setTab('bot')}>Bot control</button>
          <button className={`config-tab ${tab === 'logs' ? 'active' : ''}`} onClick={() => setTab('logs')}>Logs</button>
          <button className={`config-tab ${tab === 'admins' ? 'active' : ''}`} onClick={() => setTab('admins')}>Admins</button>
        </div>

        {tab === 'fields' && <RegistryEditor />}
        {tab === 'appearance' && <AppearanceEditor appearance={appearance} onChange={onAppearanceChange} />}
        {tab === 'bot' && <BotControl />}
        {tab === 'logs' && <LogViewer />}
        {tab === 'admins' && <AdminsEditor />}
      </main>
      <Footer />
    </div>
  );
}
