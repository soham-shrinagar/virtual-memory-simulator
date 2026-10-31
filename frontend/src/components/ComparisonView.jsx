import { useLayoutEffect, useState } from 'react';
import { compareAlgorithms } from '../api/client.js';
import useRequest from '../hooks/useRequest.js';
import { buildRequest } from '../state/simulation.js';
import { comparisonCsv, downloadFile } from '../state/files.js';

const names = { fifo: 'FIFO', lru: 'LRU', optimal: 'Optimal' };
const colors = { fifo: '#49647d', lru: '#92723d', optimal: '#547b61' };

function FaultChart({ result }) {
  const counts = [...result.frame_counts].sort((a, b) => a - b);
  const maxFaults = Math.max(1, ...result.rows.map((row) => row.metrics.faults));
  const x = (frames) => counts.length === 1 ? 330 : 52 + (frames - counts[0]) / (counts.at(-1) - counts[0]) * 556;
  const y = (faults) => 220 - faults / maxFaults * 184;
  return <figure className="fault-chart">
    <figcaption>Page faults by frame count</figcaption>
    <svg viewBox="0 0 660 270" role="img" aria-label="Fault counts for each policy. Exact values are in the results table.">
      {[0, .5, 1].map((fraction) => <g key={fraction}><line x1="52" x2="608" y1={y(maxFaults * fraction)} y2={y(maxFaults * fraction)} stroke="#ececec" /><text x="42" y={y(maxFaults * fraction) + 4} textAnchor="end">{Math.round(maxFaults * fraction)}</text></g>)}
      {counts.filter((count, index) => counts.length <= 8 || index % 4 === 0 || index === counts.length - 1).map((count) => <text key={count} x={x(count)} y="240" textAnchor="middle">{count}</text>)}
      <text x="330" y="263" textAnchor="middle">Physical frames</text>
      {result.policies.map((policy, index) => {
        const rows = result.rows.filter((row) => row.policy === policy).sort((a, b) => a.physical_frames - b.physical_frames);
        return <g key={policy} stroke={colors[policy]} fill={colors[policy]}>
          <polyline points={rows.map((row) => `${x(row.physical_frames)},${y(row.metrics.faults)}`).join(' ')} fill="none" strokeWidth="2" strokeDasharray={index === 1 ? '7 4' : index === 2 ? '2 4' : undefined} />
          {rows.map((row) => <circle key={row.physical_frames} cx={x(row.physical_frames)} cy={y(row.metrics.faults)} r="3"><title>{names[policy]}, {row.physical_frames} frames: {row.metrics.faults} faults</title></circle>)}
        </g>;
      })}
    </svg>
    <div className="chart-legend">{result.policies.map((policy) => <span key={policy} style={{ color: colors[policy] }}>{names[policy]}</span>)}</div>
  </figure>;
}

export default function ComparisonView({ draft, onBelady }) {
  const [from, setFrom] = useState('3');
  const [to, setTo] = useState('4');
  const [result, setResult] = useState(null);
  const request = useRequest();
  const reset = request.reset;
  useLayoutEffect(() => { reset(); setResult(null); }, [draft, from, to, reset]);
  const compare = (event) => {
    event.preventDefault();
    setResult(null);
    request.run(async (signal) => {
      const { policy, ...payload } = buildRequest(draft);
      const start = Number(from), end = Number(to);
      if (!/^\d+$/.test(from) || !/^\d+$/.test(to) || start < 1 || end > 32 || start > end) throw new Error('Frame range must be whole numbers from 1 to 32, with start no greater than end.');
      return compareAlgorithms({ ...payload, policies: ['fifo', 'lru', 'optimal'], frame_counts: Array.from({ length: end - start + 1 }, (_, i) => start + i) }, signal);
    }, setResult);
  };
  const anomalies = result ? result.rows.filter((row) => row.policy === 'fifo').sort((a, b) => a.physical_frames - b.physical_frames).flatMap((row, index, rows) => index && row.metrics.faults > rows[index - 1].metrics.faults ? [`${rows[index - 1].physical_frames} → ${row.physical_frames} frames: ${rows[index - 1].metrics.faults} → ${row.metrics.faults} faults`] : []) : [];
  return <section className="panel comparison-panel" aria-labelledby="comparison-title">
    <div className="section-heading"><h2 id="comparison-title">Compare algorithms</h2><button className="text-button" onClick={() => { setFrom('3'); setTo('4'); onBelady(); }}>Belady preset</button></div>
    <p className="muted-note">Every policy starts with empty memory and uses the same references. The sweep replaces the configured physical-frame count. TLB settings are shared across runs and do not change page-fault counts.</p>
    <form onSubmit={compare} className="comparison-form" aria-label="Frame sweep" noValidate>
      <label>From frames<input type="number" min="1" max="32" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
      <label>To frames<input type="number" min="1" max="32" value={to} onChange={(event) => setTo(event.target.value)} /></label>
      <button className="primary-button" disabled={request.busy}>{request.busy ? 'Comparing…' : 'Compare'}</button>
      {request.busy && <button className="button" type="button" onClick={request.reset}>Cancel comparison</button>}
    </form>
    {request.error && <p role="alert" className="form-error">{request.error}</p>}
    {result && <>
      <FaultChart result={result} />
      {anomalies.length > 0 && <p role="status" className="anomaly-note">Belady’s anomaly observed in FIFO: {anomalies.join('; ')}.</p>}
      <div className="table-scroll" tabIndex="0" role="region" aria-label="Scrollable comparison results"><table aria-label="Comparison results"><thead><tr><th scope="col">Policy</th><th scope="col">Frames</th><th scope="col">Hits</th><th scope="col">Faults</th><th scope="col">Replacements</th><th scope="col">Fault rate</th>{result.tlb_capacity > 0 && <><th scope="col">TLB hits</th><th scope="col">TLB misses</th></>}</tr></thead><tbody>
        {result.rows.map((row) => <tr key={`${row.policy}-${row.physical_frames}`}><td>{names[row.policy]}</td><td>{row.physical_frames}</td><td>{row.metrics.hits}</td><td>{row.metrics.faults}</td><td>{row.metrics.replacements}</td><td>{(row.metrics.fault_rate * 100).toFixed(2)}%</td>{row.tlb && <><td>{row.tlb.hits}</td><td>{row.tlb.misses}</td></>}</tr>)}
      </tbody></table></div>
      <button className="button csv-button" onClick={() => downloadFile('comparison.csv', comparisonCsv(result), 'text/csv;charset=utf-8')}>Export CSV</button>
    </>}
    <p className="muted-note">Optimal knows future references and is an offline benchmark. These are simulated fault counts, not measured Linux timings. Page-size changes can change the page sequence in address mode.</p>
  </section>;
}
