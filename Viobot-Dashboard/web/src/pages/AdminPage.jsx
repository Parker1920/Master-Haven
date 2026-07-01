import { useState } from 'react';
import Footer from '../components/Footer.jsx';
import RegistryEditor from '../components/RegistryEditor.jsx';
import AppearanceEditor from '../components/AppearanceEditor.jsx';
import AdminsEditor from '../components/AdminsEditor.jsx';
import BotControl from '../components/BotControl.jsx';
import LogViewer from '../components/LogViewer.jsx';
import TopBar from '../components/TopBar.jsx';

export default function AdminPage({ user, appearance, onAppearanceChange, onBack, onGuides, onLogout }) {
  const [tab, setTab] = useState('fields');

  return (
    <div className="page">
      <TopBar
        appearance={appearance}
        user={user}
        back={{ label: '‹ Servers', onClick: onBack }}
        onGuides={onGuides}
        onLogout={onLogout}
      />

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
