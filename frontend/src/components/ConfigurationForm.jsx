import { formatBytes } from '../state/simulation.js';

export default function ConfigurationForm({ draft, busy, error, onEdit, onExample, onRun, onCancel, showRun }) {
  const pages = Number(draft.virtualPages);
  const frames = Number(draft.physicalFrames);
  const size = Number(draft.pageSize);
  const validPages = Number.isInteger(pages) && pages >= 1 && pages <= 256;
  const validFrames = Number.isInteger(frames) && frames >= 1 && frames <= 32;
  const maxReference = validPages ? (draft.inputMode === 'pages' ? pages - 1 : pages * size - 1) : null;
  const change = (field) => (event) => onEdit(field, event.target.value);

  return (
    <form className="configuration panel" onSubmit={showRun ? onRun : (event) => event.preventDefault()} aria-label="Memory configuration" noValidate>
      <div className="section-heading"><h2>Configuration</h2><button className="text-button" type="button" onClick={onExample}>Load example</button></div>
      <label htmlFor="page-size">Page size</label>
      <select id="page-size" value={draft.pageSize} onChange={change('pageSize')}>
        {[256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536].map((value) => <option key={value} value={value}>{formatBytes(value)}</option>)}
      </select>
      <div className="field-pair">
        <div><label htmlFor="virtual-pages">Virtual pages</label><input id="virtual-pages" type="number" min="1" max="256" step="1" value={draft.virtualPages} onChange={change('virtualPages')} required /></div>
        <div><label htmlFor="physical-frames">Physical frames</label><input id="physical-frames" type="number" min="1" max="32" step="1" value={draft.physicalFrames} onChange={change('physicalFrames')} required /></div>
      </div>
      <dl className="capacity-list">
        <div><dt>Virtual address space</dt><dd>{validPages ? formatBytes(pages * size) : '—'}</dd></div>
        <div><dt>Physical capacity</dt><dd>{validFrames ? formatBytes(frames * size) : '—'}</dd></div>
      </dl>
      <label htmlFor="policy">Replacement policy</label>
      <select id="policy" value={draft.policy} onChange={change('policy')}>
        <option value="fifo">FIFO · First in, first out</option><option value="lru">LRU · Least recently used</option><option value="optimal">Optimal · Offline benchmark</option>
      </select>
      <label htmlFor="tlb-capacity">Translation cache (TLB)</label>
      <select id="tlb-capacity" value={draft.tlbCapacity} onChange={change('tlbCapacity')}>
        <option value="0">Disabled</option>
        {Array.from({ length: 32 }, (_, index) => index + 1).map((capacity) => <option key={capacity} value={capacity}>{capacity} {capacity === 1 ? 'entry' : 'entries'} · LRU</option>)}
      </select>
      <p className="field-hint">A TLB miss can still be a page hit. Cache capacity is separate from physical frames.</p>
      <label htmlFor="input-mode">Reference type</label>
      <select id="input-mode" value={draft.inputMode} onChange={change('inputMode')}>
        <option value="pages">Page numbers</option><option value="addresses">Virtual byte addresses</option>
      </select>
      <label htmlFor="workload">Memory references</label>
      <textarea id="workload" rows="4" value={draft.workload} onChange={change('workload')} maxLength="65536" aria-describedby="workload-hint" spellCheck="false" />
      <p id="workload-hint" className="field-hint">Separate with commas or spaces. Up to 1,000 references.{maxReference !== null && <> Range: 0–{maxReference.toLocaleString('en-US')}.</>}{draft.inputMode === 'addresses' && ' Hexadecimal (0x) is also accepted.'}</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      {showRun && <div className="run-actions">
        <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Preparing trace…' : 'Run simulation'}</button>
        {busy && <button className="button" type="button" onClick={onCancel}>Cancel</button>}
      </div>}
      <p className="field-hint form-footnote">Editing a setting starts a new experiment.</p>
    </form>
  );
}
