import { useEffect, useReducer, useRef, useState } from 'react';
import { exportExperiment, getHealth, importExperiment, simulateExperiment } from './api/client.js';
import ComparisonView from './components/ComparisonView.jsx';
import ConfigurationForm from './components/ConfigurationForm.jsx';
import SimulationView from './components/SimulationView.jsx';
import WorkloadGenerator from './components/WorkloadGenerator.jsx';
import usePlayback from './hooks/usePlayback.js';
import useRequest from './hooks/useRequest.js';
import { downloadFile, experimentDraft } from './state/files.js';
import { buildRequest, initialState, simulationReducer } from './state/simulation.js';

export default function App() {
  const [connection, setConnection] = useState({ status: 'checking' });
  const [attempt, setAttempt] = useState(0);
  const [simulation, dispatch] = useReducer(simulationReducer, initialState);
  const playback = usePlayback(simulation.trace);
  const simulationRequest = useRequest();
  const [view, setView] = useState('simulator');
  const fileRequest = useRequest();
  const fileInput = useRef(null);

  const edit = (field, value) => {
    fileRequest.reset();
    simulationRequest.reset();
    dispatch({ type: 'EDIT', field, value });
  };

  const loadExample = () => {
    fileRequest.reset();
    simulationRequest.reset();
    dispatch({ type: 'EXAMPLE' });
  };

  const loadDraft = (draft) => {
    simulationRequest.reset();
    dispatch({ type: 'LOAD', draft });
  };

  const loadBelady = () => {
    fileRequest.reset();
    simulationRequest.reset();
    dispatch({ type: 'BELADY' });
  };

  const save = () => fileRequest.run((signal) => exportExperiment(buildRequest(simulation.draft), signal),
    (experiment) => downloadFile('experiment.json', JSON.stringify(experiment, null, 2) + '\n', 'application/json'));
  const open = (event) => {
    const file = event.target.files[0];
    event.target.value = '';
    if (!file) return;
    playback.pause();
    fileRequest.run(async (signal) => {
      if (file.size > 131072) throw new Error('Experiment files must be at most 128 KiB.');
      let text;
      try { text = await file.text(); }
      catch { throw new Error('Unable to read the experiment file.'); }
      if (signal.aborted) throw new Error('Import canceled.');
      return importExperiment(text, signal);
    }, (experiment) => loadDraft(experimentDraft(experiment)));
  };

  const cancel = () => {
    simulationRequest.reset();
    dispatch({ type: 'CLEAR_TRACE' });
  };

  const run = (event) => {
    event.preventDefault();
    dispatch({ type: 'CLEAR_TRACE' });
    simulationRequest.run(
      (signal) => simulateExperiment(buildRequest(simulation.draft), signal),
      (trace) => dispatch({ type: 'SUCCESS', trace }),
    );
  };

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
        <section aria-labelledby="page-title">
          <p className="eyebrow">Operating systems / Memory</p>
          <h1 id="page-title">Virtual memory</h1>
          <p className="page-description">Run a trace. Follow each address. See every memory decision.</p>
        </section>

        {connection.status === 'error' && (
          <p className="connection-error">Unable to reach the local server. Start the Python server and check the connection again.</p>
        )}

        <div className="workspace-toolbar">
          <nav aria-label="Workspace view">{['simulator', 'compare'].map((name) => <button key={name} className="view-button" aria-label={`${name} view`} aria-pressed={view === name} onClick={() => { playback.pause(); setView(name); }}>{name === 'simulator' ? 'Simulator' : 'Compare'}</button>)}</nav>
          <div className="file-actions">
            <button className="button" disabled={fileRequest.busy} onClick={save}>Save JSON</button>
            <button className="button" disabled={fileRequest.busy} onClick={() => fileInput.current.click()}>Load JSON</button>
            <input ref={fileInput} type="file" accept=".json,application/json" aria-label="Experiment file" hidden onChange={open} />
            {fileRequest.busy && <button className="button" onClick={fileRequest.reset}>Cancel file operation</button>}
          </div>
        </div>
        {fileRequest.error && <p className="form-error" role="alert">{fileRequest.error}</p>}
        <div className="simulator-layout">
          <div className="simulation-setup">
          <ConfigurationForm
            draft={simulation.draft}
            busy={simulationRequest.busy}
            error={simulationRequest.error}
            onEdit={edit}
            onExample={loadExample}
            onRun={run}
            onCancel={cancel}
            showRun={view === 'simulator'}
          />
          <WorkloadGenerator draft={simulation.draft} onGenerated={(workload) => edit('workload', workload)} />
          </div>
          {view === 'simulator'
            ? <SimulationView trace={simulation.trace} busy={simulationRequest.busy} playback={playback} />
            : <ComparisonView draft={simulation.draft} onBelady={loadBelady} />}
        </div>
      </main>

      <footer className="app-footer">
        <span>Virtual Memory Simulator</span>
        <span>Local workspace{connection.status === 'connected' && <span className="app-version">v{connection.health.version}</span>}</span>
      </footer>
    </div>
  );
}
