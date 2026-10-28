import { useEffect, useState } from 'react';
import { getHealth } from './api/client.js';

export default function App() {
  const [connection, setConnection] = useState({ status: 'checking' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    let active = true;
    setConnection({ status: 'checking' });
    getHealth(controller.signal)
      .then((health) => { if (active) setConnection({ status: 'connected', health }); })
      .catch(() => { if (active) setConnection({ status: 'error' }); })
      .finally(() => window.clearTimeout(timeout));
    return () => { active = false; window.clearTimeout(timeout); controller.abort(); };
  }, [attempt]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="/" aria-label="VM Lab home">
          <span className="brand-icon" aria-hidden="true">
            <svg viewBox="0 0 20 20" fill="none">
              <rect x="3" y="3" width="5" height="5" rx="1" />
              <rect x="12" y="3" width="5" height="5" rx="1" />
              <rect x="3" y="12" width="5" height="5" rx="1" />
              <rect x="12" y="12" width="5" height="5" rx="1" />
            </svg>
          </span>
          <span>VM Lab</span>
        </a>
        <div className="header-status">
          <div className="connection" role="status" aria-live="polite">
            <span className={`status-dot ${connection.status}`} aria-hidden="true" />
            {connection.status === 'checking' && 'Connecting'}
            {connection.status === 'connected' && 'Connected'}
            {connection.status === 'error' && 'Offline'}
          </div>
          <button
            className="refresh-button"
            aria-label="Check connection"
            title="Check connection"
            disabled={connection.status === 'checking'}
            onClick={() => setAttempt((value) => value + 1)}
          >
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M15.5 7a6 6 0 1 0 .2 5.5M15.5 3.5V7H12" />
            </svg>
          </button>
        </div>
      </header>

      <main>
        <section className="page-heading" aria-labelledby="page-title">
          <p className="eyebrow">Operating systems / Memory</p>
          <h1 id="page-title">Virtual memory</h1>
          <p className="page-description">Understand paging, address translation, and replacement policies.</p>
        </section>

        {connection.status === 'error' && (
          <p className="connection-error">Unable to reach the local server. Start the Python API on port 8000 and check the connection again.</p>
        )}

        <section className="workspace" aria-labelledby="workspace-title">
          <div className="workspace-header">
            <h2 id="workspace-title">Workspace</h2>
            <span className="workspace-state">Not configured</span>
          </div>
          <div className="empty-state">
            <div className="memory-icon" aria-hidden="true">
              <svg viewBox="0 0 32 32" fill="none">
                <rect x="7" y="5" width="18" height="22" rx="3" />
                <path d="M7 12.5h18M7 19.5h18M11 9h1M11 16h1M11 23h1" />
              </svg>
            </div>
            <h3>A place to explore memory.</h3>
            <p>Configure a memory model, follow each address,<br className="desktop-break" /> and see how every decision unfolds.</p>
            <span className="upcoming-note">Configuration tools are coming next.</span>
          </div>
          <div className="workspace-footer">
            <span>Single-process simulation</span>
            <span>FIFO <span className="separator">/</span> LRU <span className="separator">/</span> Optimal</span>
          </div>
        </section>
      </main>

      <footer className="app-footer">
        <span>Virtual Memory Simulator</span>
        <span>Local workspace{connection.status === 'connected' && <span className="app-version">v{connection.health.version}</span>}</span>
      </footer>
    </div>
  );
}

