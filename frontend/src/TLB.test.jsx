import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App.jsx';
import { validateSimulation } from './api/client.js';
import contracts from './test/fixtures/contracts.json';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('renders selected-step cache counters, restores them backward, and sends capacity', async () => {
  const fetcher = vi.fn(async (url) => ({ ok: true, json: async () => url === '/api/health'
    ? { status: 'ok', application: 'vmsim', version: '0.1.0', frontend_ready: true }
    : contracts.tlb_simulation }));
  vi.stubGlobal('fetch', fetcher);
  render(<App />);
  fireEvent.change(screen.getByLabelText('Translation cache (TLB)'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
  await screen.findByRole('heading', { name: 'Physical memory' });
  fireEvent.change(screen.getByLabelText('Simulation step'), { target: { value: '3' } });
  expect(screen.getByRole('region', { name: 'Translation cache' })).toHaveTextContent('Cache hits: 1 · misses: 2');
  fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
  expect(screen.getByRole('region', { name: 'Translation cache' })).toHaveTextContent('Cache hits: 0 · misses: 2');
  expect(JSON.parse(fetcher.mock.calls.find(([url]) => url === '/api/simulate')[1].body).tlb_capacity).toBe(2);
});

it('rejects a cached frame that disagrees with the page table and a corrupt lookup count', () => {
  expect(validateSimulation(contracts.tlb_simulation)).toBe(contracts.tlb_simulation);
  const trace = structuredClone(contracts.tlb_simulation);
  trace.events[0].state.tlb.entries[0].frame_id = 1;
  expect(() => validateSimulation(trace)).toThrow();
  const counts = structuredClone(contracts.tlb_simulation);
  counts.events[2].state.tlb.hits = 0;
  expect(() => validateSimulation(counts)).toThrow();
});
