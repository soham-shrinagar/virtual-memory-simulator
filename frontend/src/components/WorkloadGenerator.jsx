import { useLayoutEffect, useState } from 'react';
import { generateWorkload } from '../api/client.js';
import useRequest from '../hooks/useRequest.js';
import { buildMemoryConfig, parseInteger } from '../state/simulation.js';

export default function WorkloadGenerator({ draft, onGenerated }) {
  const [seed, setSeed] = useState('42');
  const [length, setLength] = useState('100');
  const [profile, setProfile] = useState('locality');
  const request = useRequest();
  const reset = request.reset;
  useLayoutEffect(() => { reset(); }, [draft, seed, length, profile, reset]);
  const generate = (event) => {
    event.preventDefault();
    request.run((signal) => generateWorkload({
      config: buildMemoryConfig(draft), input_mode: draft.inputMode, profile,
      seed: parseInteger(seed, 'Seed', 0, 4294967295),
      length: parseInteger(length, 'Reference count', 1, 1000),
    }, signal), (result) => onGenerated(result.workload.join(', ')));
  };
  return <details className="panel generator-panel">
    <summary>Generate references</summary>
    <form className="configuration" onSubmit={generate} aria-label="Workload generator" noValidate>
      <label htmlFor="generator-profile">Workload profile</label>
      <select id="generator-profile" value={profile} onChange={(event) => setProfile(event.target.value)}>
        <option value="locality">Locality · shifting hot set</option><option value="uniform">Uniform · random pages</option><option value="sequential">Sequential · cycling pages</option>
      </select>
      <div className="field-pair">
        <div><label htmlFor="generator-seed">Seed</label><input id="generator-seed" type="number" min="0" max="4294967295" value={seed} onChange={(event) => setSeed(event.target.value)} /></div>
        <div><label htmlFor="generator-length">Reference count</label><input id="generator-length" type="number" min="1" max="1000" value={length} onChange={(event) => setLength(event.target.value)} /></div>
      </div>
      <p className="field-hint">Uses the configured page range and input mode. Locality favors a hot set of up to four pages (80%), moving every 32 references. Same seed and settings reproduce the same list.</p>
      {request.error && <p className="form-error" role="alert">{request.error}</p>}
      <div className="run-actions"><button className="button" disabled={request.busy}>{request.busy ? 'Generating…' : 'Generate workload'}</button>{request.busy && <button className="button" type="button" onClick={reset}>Cancel generation</button>}</div>
      <p className="field-hint">Replaces the editor and clears the active trace. JSON saves the generated references.</p>
    </form>
  </details>;
}
