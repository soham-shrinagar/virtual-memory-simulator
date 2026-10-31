import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App.jsx';
import { validateSimulation } from './api/client.js';
import contracts from './test/fixtures/contracts.json';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('renders CLOCK hand and bits and restores them on backward playback', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url) => ({ ok: true, json: async () => url === '/api/health'
    ? { status: 'ok', application: 'vmsim', version: '0.1.0', frontend_ready: true }
    : contracts.clock_simulation })));
  render(<App />);
  fireEvent.change(screen.getByLabelText('Replacement policy'), { target: { value: 'clock' } });
  fireEvent.change(screen.getByLabelText('Memory references'), { target: { value: '0, 1, 2, 0, 3, 1, 4' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
  await screen.findByRole('heading', { name: 'Physical memory' });
  fireEvent.change(screen.getByLabelText('Simulation step'), { target: { value: '5' } });
  const metadata = screen.getByRole('region', { name: 'Policy state' });
  expect(metadata).toHaveTextContent('Hand → F1');
  expect(metadata).toHaveTextContent('Reference bit 0');
  expect(screen.getByText(/CLOCK evicted page 0/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
  expect(metadata).toHaveTextContent('Hand → F0');
  expect(metadata).not.toHaveTextContent('Reference bit 0');
});

it('rejects invalid CLOCK hand and reference-bit metadata', () => {
  expect(validateSimulation(contracts.clock_simulation)).toBe(contracts.clock_simulation);
  const trace = structuredClone(contracts.clock_simulation);
  trace.events[0].state.policy_state.hand = 32;
  expect(() => validateSimulation(trace)).toThrow();
  const bits = structuredClone(contracts.clock_simulation);
  bits.events[2].state.policy_state.reference_bits[0].referenced = 1;
  expect(() => validateSimulation(bits)).toThrow();
});
