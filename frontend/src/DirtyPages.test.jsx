import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App.jsx';
import { validateSimulation } from './api/client.js';
import { comparisonCsv, experimentDraft } from './state/files.js';
import contracts from './test/fixtures/contracts.json';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('revisits dirty bits and writebacks independently of cache hits', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url) => ({ ok: true, json: async () => url === '/api/health'
    ? { status: 'ok', application: 'vmsim', version: '0.1.0', frontend_ready: true }
    : contracts.dirty_simulation })));
  render(<App />);
  fireEvent.change(screen.getByLabelText('Physical frames'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Memory references'), { target: { value: 'W:0 R:0 1 0 W:0 W:0 2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
  await screen.findByRole('heading', { name: 'Physical memory' });
  const timeline = screen.getByLabelText('Simulation step');
  fireEvent.change(timeline, { target: { value: '3' } });
  expect(screen.getByLabelText('Writebacks')).toHaveTextContent('1');
  expect(screen.getByTestId('frame-0')).toHaveTextContent('Clean');
  expect(within(screen.getByRole('table', { name: 'Reference history' })).getAllByText('Write')).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
  expect(screen.getByLabelText('Writebacks')).toHaveTextContent('0');
  expect(screen.getByTestId('frame-0')).toHaveTextContent('Dirty');
  fireEvent.change(timeline, { target: { value: '7' } });
  expect(screen.getByLabelText('Reads', { exact: true })).toHaveTextContent('4');
  expect(screen.getByLabelText('Writes', { exact: true })).toHaveTextContent('3');
  expect(screen.getByLabelText('Writebacks')).toHaveTextContent('2');
  fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
  expect(screen.getByTestId('frame-0')).toHaveTextContent('Empty');
  expect(screen.getByLabelText('Writes', { exact: true })).toHaveTextContent('0');
});

it.each([
  (data) => { data.events[2].writeback = false; },
  (data) => { data.events[1].state.frames[0].dirty = false; },
  (data) => { data.operations[0] = 'read'; },
  (data) => { data.metrics.writebacks = 1; },
])('rejects inconsistent operations, dirty state, or writeback totals', (corrupt) => {
  expect(validateSimulation(contracts.dirty_simulation)).toBe(contracts.dirty_simulation);
  const trace = structuredClone(contracts.dirty_simulation);
  corrupt(trace);
  expect(() => validateSimulation(trace)).toThrow(/Unexpected/);
});

it('restores write prefixes and appends operation counts to CSV', () => {
  expect(experimentDraft({
    ...contracts.experiment, workload: [0, 1, 0], operations: ['write', 'read', 'write'],
  }).workload).toBe('W:0, 1, W:0');
  const lines = comparisonCsv(contracts.comparison).trimEnd().split('\r\n');
  expect(lines[0]).toMatch(/,reads,writes,writebacks$/);
  expect(lines[1]).toMatch(/,4,0,0$/);
});
