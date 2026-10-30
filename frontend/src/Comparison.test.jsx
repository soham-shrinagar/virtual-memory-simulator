import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App.jsx';
import contracts from './test/fixtures/contracts.json';
import { comparisonCsv } from './state/files.js';

const response = (data) => ({ ok: true, json: async () => data });
const health = { status: 'ok', application: 'vmsim', version: '0.1.0', phase: 5, frontend_ready: true };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function mount(handler = () => response(contracts.comparison)) {
  const fetcher = vi.fn((url, options) => Promise.resolve(url === '/api/health' ? response(health) : handler(url, JSON.parse(options.body), options)));
  vi.stubGlobal('fetch', fetcher);
  render(<App />);
  return fetcher;
}
function compareView() { fireEvent.click(screen.getByRole('button', { name: 'compare view' })); }

it('sends a fresh sweep, renders exact API metrics, and exports raw CSV rates', async () => {
  const fetcher = mount(); compareView();
  fireEvent.change(screen.getByLabelText('From frames'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('To frames'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Compare', exact: true }));
  const table = await screen.findByRole('table', { name: 'Comparison results' });
  expect(within(table).getAllByRole('row')).toHaveLength(7);
  expect(screen.getByRole('img')).toHaveAccessibleName(/Fault counts/);
  const request = fetcher.mock.calls.find(([url]) => url === '/api/compare');
  expect(JSON.parse(request[1].body)).toMatchObject({ frame_counts: [1, 2], policies: ['fifo', 'lru', 'optimal'] });
  expect(JSON.parse(request[1].body)).not.toHaveProperty('policy');
  const csv = comparisonCsv(contracts.comparison);
  expect(csv.split('\r\n')).toHaveLength(8);
  const row = contracts.comparison.rows[0];
  expect(csv).toContain(`${row.policy},${row.physical_frames},4,${row.metrics.hits},${row.metrics.faults},${row.metrics.replacements},${row.metrics.hit_rate},${row.metrics.fault_rate}`);
});

it('loads the Belady preset and reports the 9 to 10 fault increase', async () => {
  mount(() => {
    const data = structuredClone(contracts.comparison);
    data.input_mode = 'pages'; data.workload = [1,2,3,4,1,2,5,1,2,3,4,5]; data.frame_counts = [3,4];
    data.rows.forEach((row, index) => {
      const faults = [9,10,7,10,8,6][index];
      row.physical_frames = index < 3 ? 3 : 4;
      row.metrics = { references: 12, faults, hits: 12-faults, replacements: faults-row.physical_frames, hit_rate: (12-faults)/12, fault_rate: faults/12 };
    });
    return response(data);
  });
  compareView(); fireEvent.click(screen.getByRole('button', { name: 'Belady preset' }));
  expect(screen.getByLabelText('Memory references')).toHaveValue('1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5');
  fireEvent.click(screen.getByRole('button', { name: 'Compare', exact: true }));
  expect(await screen.findByText(/Belady’s anomaly observed/)).toHaveTextContent('3 → 4 frames: 9 → 10 faults');
});

it('rejects invalid sweeps and clears obsolete comparison results after edits', async () => {
  const fetcher = mount(); compareView();
  fireEvent.change(screen.getByLabelText('From frames'), { target: { value: '5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Compare', exact: true }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Frame range');
  expect(fetcher.mock.calls.filter(([url]) => url === '/api/compare')).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('From frames'), { target: { value: '1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Compare', exact: true }));
  await screen.findByRole('table');
  fireEvent.change(screen.getByLabelText('Memory references'), { target: { value: '0' } });
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

it('aborts comparison on edits and ignores late results', async () => {
  let finish;
  const fetcher = mount(() => new Promise((resolve) => { finish = resolve; })); compareView();
  fireEvent.click(screen.getByRole('button', { name: 'Compare', exact: true }));
  const signal = fetcher.mock.calls.find(([url]) => url === '/api/compare')[1].signal;
  fireEvent.change(screen.getByLabelText('Physical frames'), { target: { value: '4' } });
  expect(signal.aborted).toBe(true);
  await act(async () => finish(response(contracts.comparison)));
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});

it('imports a validated experiment and preserves the draft on malformed files', async () => {
  const fetcher = mount(() => response(contracts.experiment));
  const file = { size: 100, text: async () => JSON.stringify(contracts.experiment) };
  fireEvent.change(screen.getByLabelText('Experiment file'), { target: { files: [file] } });
  await screen.findByDisplayValue('0, 4097, 0, 8194');
  expect(screen.getByLabelText('Reference type')).toHaveValue('addresses');
  expect(screen.getByLabelText('Physical frames')).toHaveValue(2);
  expect(fetcher.mock.calls.find(([url]) => url === '/api/experiments/import')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Experiment file'), { target: { files: [{ size: 3, text: async () => 'bad' }] } });
  expect(await screen.findByRole('alert')).toHaveTextContent('valid JSON');
  expect(screen.getByLabelText('Memory references')).toHaveValue('0, 4097, 0, 8194');
});

it('downloads validated JSON and releases the object URL', async () => {
  const create = vi.fn(() => 'blob:test');
  vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  const fetcher = mount(() => response(contracts.experiment));
  fireEvent.click(screen.getByRole('button', { name: 'Save JSON' }));
  await vi.waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(create).toHaveBeenCalledWith(expect.any(Blob));
  expect(JSON.parse(fetcher.mock.calls.find(([url]) => url === '/api/experiments/export')[1].body).schema_version).toBe(1);
  await vi.waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test'), { timeout: 2000 });
});

