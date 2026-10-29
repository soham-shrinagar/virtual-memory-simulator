import PlaybackControls from './PlaybackControls.jsx';

const policyNames = { fifo: 'FIFO', lru: 'LRU', optimal: 'Optimal' };
const rate = (value) => value === null ? '—' : `${(value * 100).toFixed(1)}%`;

function MetricsPanel({ metrics }) {
  return <section className="metrics" aria-label="Selected step metrics">
    {[['References', metrics.references], ['Hits', metrics.hits], ['Faults', metrics.faults], ['Replacements', metrics.replacements]].map(([label, value]) =>
      <div key={label}><span>{label}</span><output aria-label={label}>{value}</output></div>)}
    <p>Hit rate <strong>{rate(metrics.hit_rate)}</strong><span>·</span>Fault rate <strong>{rate(metrics.fault_rate)}</strong></p>
  </section>;
}

function FrameView({ snapshot, event }) {
  return <ul className="frames" aria-label="Physical frames">{snapshot.frames.map((frame) => {
    const selected = event?.frame_id === frame.frame_id;
    const action = selected ? (event.result === 'hit' ? 'Hit' : event.victim_page !== null ? `Replaced P${event.victim_page}` : 'Loaded') : '';
    return <li key={frame.frame_id} className={`frame ${selected ? event.result : ''}`} data-testid={`frame-${frame.frame_id}`} aria-label={`Frame ${frame.frame_id}, ${frame.page === null ? 'empty' : `page ${frame.page}`}${action ? `, ${action}` : ''}`}>
      <span className="frame-label">F{frame.frame_id}</span><strong>{frame.page === null ? '—' : `P${frame.page}`}</strong><span className="frame-action">{action || (frame.page === null ? 'Empty' : 'Resident')}</span>
    </li>;
  })}</ul>;
}

function AddressBreakdown({ event, config }) {
  return <section className="address-section" aria-labelledby="translation-title">
    <h2 id="translation-title">Address translation</h2>
    {event ? <>
      <dl className="address-values">{[['Virtual address', event.virtual_address], ['Page', event.page], ['Offset', event.offset], ['Physical address', event.physical_address]].map(([label, value]) =>
        <div key={label}><dt>{label}</dt><dd><output aria-label={label}>{value.toLocaleString('en-US')}</output></dd></div>)}</dl>
      <div className="equations"><code>{event.virtual_address} ÷ {config.page_size} → page {event.page}, offset {event.offset}</code><code>F{event.frame_id} × {config.page_size} + {event.offset} = {event.physical_address}</code></div>
    </> : <p className="muted-note">Advance one step to translate the first address.</p>}
  </section>;
}

function PageTable({ snapshot, config, event }) {
  const mapping = new Map(snapshot.resident_pages.map((entry) => [entry.page, entry.frame_id]));
  return <section className="panel detail-panel" aria-labelledby="page-table-title">
    <div className="section-heading"><h2 id="page-table-title">Page table</h2><span className="small-note">{mapping.size} / {config.virtual_pages} resident</span></div>
    <div className="table-scroll page-table-scroll"><table aria-label="Page table"><thead><tr><th>Page</th><th>State</th><th>Frame</th></tr></thead><tbody>
      {Array.from({ length: config.virtual_pages }, (_, page) => <tr key={page} className={event?.page === page ? 'current-row' : ''}>
        <td>P{page}</td><td>{mapping.has(page) ? 'Resident' : <span className="muted">Not resident</span>}</td><td>{mapping.has(page) ? `F${mapping.get(page)}` : '—'}</td>
      </tr>)}
    </tbody></table></div>
  </section>;
}

function PolicyState({ snapshot, policy }) {
  const metadata = snapshot.policy_state;
  const page = (frame) => snapshot.frames[frame].page;
  const lastAccess = new Map(metadata.last_access.map((entry) => [entry.frame_id, entry.step]));
  return <section className="panel detail-panel" aria-labelledby="policy-title">
    <div className="section-heading"><h2 id="policy-title">Policy state</h2><span className="small-note">{policyNames[policy]}</span></div>
    <p className="muted-note">{policy === 'fifo' ? 'Arrival order · oldest first' : policy === 'lru' ? 'Access order · least recent first' : 'Next reference for each resident page'}</p>
    {snapshot.resident_pages.length === 0 ? <p className="muted-note">No resident pages.</p> : policy === 'optimal' ?
      <ul className="policy-list">{metadata.next_use.map((entry) => <li key={entry.frame_id}><span>P{page(entry.frame_id)} <small>F{entry.frame_id}</small></span><span>{entry.step === null ? 'Never used again' : `Step ${entry.step}`}</span></li>)}</ul> :
      <ol className="policy-order">{metadata.order.map((frame) => <li key={frame}><strong>P{page(frame)}</strong><span>F{frame}{policy === 'lru' && ` · step ${lastAccess.get(frame)}`}</span></li>)}</ol>}
    {policy === 'optimal' && <p className="field-hint">Offline benchmark using the complete workload.</p>}
  </section>;
}

function History({ trace, cursor, onSeek }) {
  const start = Math.max(0, cursor - 12);
  const visible = trace.events.slice(start, cursor);
  return <section className="panel history-panel" aria-labelledby="history-title">
    <div className="section-heading"><h2 id="history-title">Reference history</h2><span className="small-note">{cursor ? `Steps ${start + 1}–${cursor}` : 'No completed references'}</span></div>
    {cursor === 0 ? <p className="muted-note">Completed references appear here. Select a step to revisit its state.</p> :
      <div className="table-scroll"><table aria-label="Reference history"><thead><tr><th>Step</th><th>Page</th><th>Result</th><th>Frame</th><th>Evicted</th><th>Physical address</th></tr></thead><tbody>
        {visible.map((event) => <tr key={event.step} className={event.step === cursor ? 'current-row' : ''}>
          <td><button className="step-link" onClick={() => onSeek(event.step)} aria-label={`Go to step ${event.step}`}>{event.step}</button></td><td>P{event.page}</td><td><span className={`result-text ${event.result}`}>{event.result === 'hit' ? 'Hit' : 'Fault'}</span></td><td>F{event.frame_id}</td><td>{event.victim_page === null ? '—' : `P${event.victim_page}`}</td><td>{event.physical_address.toLocaleString('en-US')}</td>
        </tr>)}
      </tbody></table></div>}
    {cursor > 12 && <p className="field-hint history-hint">Showing the latest 12 completed references. Use the timeline to reach any step.</p>}
  </section>;
}

export default function SimulationView({ trace, status, playback }) {
  if (!trace) return <section className="panel empty-workspace" aria-label="Simulation workspace" aria-busy={status === 'loading'}>
    <span className="empty-symbol" aria-hidden="true">[ &nbsp; ]</span><h2>{status === 'loading' ? 'Preparing your trace…' : 'Your memory workspace'}</h2><p>{status === 'loading' ? 'Calculating each reference and memory decision.' : 'Choose a memory model, then run a simulation.'}</p><span className="small-note">FIFO / LRU / Optimal</span>
  </section>;

  const { cursor } = playback;
  const event = cursor ? trace.events[cursor - 1] : null;
  const snapshot = event?.state ?? trace.initial_state;
  const next = trace.events[cursor];
  return <div className="simulation-results" aria-label="Simulation workspace">
    <section className="panel memory-panel" aria-labelledby="memory-title">
      <div className="section-heading memory-heading"><div><h2 id="memory-title">Physical memory</h2><span className="small-note">{trace.config.physical_frames} frames · {policyNames[trace.policy]}</span></div><span className={`result-badge ${event?.result ?? ''}`}>{event ? event.result === 'hit' ? 'Page hit' : 'Page fault' : 'Initial state'}</span></div>
      <MetricsPanel metrics={snapshot.metrics} />
      <FrameView snapshot={snapshot} event={event} />
      <p className="event-explanation" role="status">{event ? event.reason : 'All frames are empty. Advance to the first reference.'}</p>
      <PlaybackControls playback={playback} ready />
      <div className="trace-summary"><span>{next ? `Next: ${trace.input_mode === 'pages' ? `P${next.page}` : `address ${next.virtual_address.toLocaleString('en-US')}`}` : 'End of trace'}</span><span>Run totals: {trace.metrics.faults} {trace.metrics.faults === 1 ? 'fault' : 'faults'} · {trace.metrics.hits} {trace.metrics.hits === 1 ? 'hit' : 'hits'}</span></div>
      <AddressBreakdown event={event} config={trace.config} />
    </section>
    <div className="detail-grid"><PageTable snapshot={snapshot} config={trace.config} event={event} /><PolicyState snapshot={snapshot} policy={trace.policy} /></div>
    <History trace={trace} cursor={cursor} onSeek={playback.seek} />
  </div>;
}
