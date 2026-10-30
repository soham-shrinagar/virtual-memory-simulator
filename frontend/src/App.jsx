import { useEffect, useReducer, useRef, useState } from 'react';
import { exportExperiment, getHealth, importExperiment, simulateExperiment } from './api/client.js';
import ComparisonView from './components/ComparisonView.jsx';
import useRequest from './hooks/useRequest.js';
import { downloadFile, experimentDraft } from './state/files.js';
import ConfigurationForm from './components/ConfigurationForm.jsx';
import SimulationView from './components/SimulationView.jsx';
import usePlayback from './hooks/usePlayback.js';
import { buildRequest, initialState, simulationReducer } from './state/simulation.js';

export default function App() {
  const [connection, setConnection] = useState({ status: 'checking' });
  const [attempt, setAttempt] = useState(0);
  const [simulation, dispatch] = useReducer(simulationReducer, initialState);
  const playback = usePlayback(simulation.trace);
  const generation = useRef(0);
  const activeRequest = useRef(null);
  const [view, setView] = useState('simulator');
  const fileRequest = useRequest();
  const fileInput = useRef(null);

  const invalidateRequest = () => {
    generation.current += 1;
    if (activeRequest.current) {
      window.clearTimeout(activeRequest.current.timer);
      activeRequest.current.controller.abort();
      activeRequest.current = null;
    }
  };

  useEffect(() => () => invalidateRequest(), []);

  const edit = (field, value) => {
    fileRequest.reset();
    invalidateRequest();
    playback.reset();
    dispatch({ type: 'EDIT', field, value });
  };

  const loadExample = () => {
    fileRequest.reset();
    invalidateRequest();
    playback.reset();
    dispatch({ type: 'EXAMPLE' });
  };

  const loadDraft = (draft) => {
    invalidateRequest();
    playback.reset();
    dispatch({ type: 'LOAD', draft });
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
      catch { throw new Error('Choose a valid JSON experiment file.'); }
      if (signal.aborted) throw new Error('Import canceled.');
      return importExperiment(text, signal);
    }, (experiment) => loadDraft(experimentDraft(experiment)));
  };

  const cancel = () => {
    invalidateRequest();
    playback.reset();
    dispatch({ type: 'CANCEL' });
  };

  const run = (event) => {
    event.preventDefault();
    if (activeRequest.current) return;
    playback.reset();
    let request;
    try { request = buildRequest(simulation.draft); }
    catch (error) { dispatch({ type: 'FAIL', message: error.message }); return; }
    dispatch({ type: 'START' });
    const token = ++generation.current;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      if (generation.current !== token) return;
      invalidateRequest();
      dispatch({ type: 'FAIL', message: 'The request timed out. Check the local server and try again.' });
    }, 15000);
    activeRequest.current = { controller, timer };
    simulateExperiment(request, controller.signal)
      .then((trace) => {
        if (generation.current !== token) return;
        window.clearTimeout(timer);
        activeRequest.current = null;
        dispatch({ type: 'SUCCESS', trace });
      })
      .catch((error) => {
        if (generation.current !== token) return;
        window.clearTimeout(timer);
        activeRequest.current = null;
        dispatch({ type: 'FAIL', message: error.message || 'Unable to prepare the simulation.' });
      });
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
        <section className="page-heading" aria-labelledby="page-title">
          <p className="eyebrow">Operating systems / Memory</p>
          <h1 id="page-title">Virtual memory</h1>
          <p className="page-description">Run a trace. Follow each address. See every memory decision.</p>
        </section>

        {connection.status === 'error' && (
          <p className="connection-error">Unable to reach the local server. Start the Python API on port 8000 and check the connection again.</p>
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
          <ConfigurationForm draft={simulation.draft} status={simulation.status} error={simulation.error} onEdit={edit} onExample={loadExample} onRun={run} onCancel={cancel} showRun={view === 'simulator'} />
          {view === 'simulator' ? <SimulationView trace={simulation.trace} status={simulation.status} playback={playback} />
            : <ComparisonView draft={simulation.draft} onBelady={() => { fileRequest.reset(); loadDraft({ pageSize: '4096', virtualPages: '8', physicalFrames: '3', inputMode: 'pages', policy: 'fifo', workload: '1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5' }); }} />}
        </div>
      </main>

      <footer className="app-footer">
        <span>Virtual Memory Simulator</span>
        <span>Local workspace{connection.status === 'connected' && <span className="app-version">v{connection.health.version}</span>}</span>
      </footer>
    </div>
  );
}
