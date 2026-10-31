import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App.jsx';
import contracts from './test/fixtures/contracts.json';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount(generate = () => Promise.resolve({ ok: true, json: async () => contracts.generated_workload })) {
  const fetcher = vi.fn((url, options) => url === '/api/health'
    ? Promise.resolve({ ok: true, json: async () => ({ status: 'ok', application: 'vmsim', version: '0.1.0', frontend_ready: true }) })
    : generate(url, options));
  vi.stubGlobal('fetch', fetcher);
  render(<App />);
  fireEvent.click(screen.getByText('Generate references'));
  fireEvent.change(screen.getByLabelText('Workload profile'), { target: { value: 'uniform' } });
  fireEvent.change(screen.getByLabelText('Reference count'), { target: { value: '5' } });
  return fetcher;
}

it('generates with the current settings even when the editor is empty', async () => {
  const fetcher = mount();
  fireEvent.change(screen.getByLabelText('Memory references'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'Generate workload' }));
  await screen.findByDisplayValue('0, 2, 1, 5, 5');
  const payload = JSON.parse(fetcher.mock.calls.find(([url]) => url === '/api/workloads/generate')[1].body);
  expect(payload).toEqual({ config: { page_size: 4096, virtual_pages: 8, physical_frames: 3 }, input_mode: 'pages', seed: 42, length: 5, profile: 'uniform' });
});

it('rejects invalid seeds locally and preserves manually edited references after a stale response', async () => {
  let finish;
  const fetcher = mount(() => new Promise((resolve) => { finish = resolve; }));
  fireEvent.change(screen.getByLabelText('Seed', { exact: true }), { target: { value: '-1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Generate workload' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Seed must be an integer');
  expect(fetcher.mock.calls.filter(([url]) => url === '/api/workloads/generate')).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('Seed', { exact: true }), { target: { value: '42' } });
  fireEvent.click(screen.getByRole('button', { name: 'Generate workload' }));
  const signal = fetcher.mock.calls.find(([url]) => url === '/api/workloads/generate')[1].signal;
  fireEvent.change(screen.getByLabelText('Memory references'), { target: { value: '7, 7' } });
  expect(signal.aborted).toBe(true);
  await act(async () => finish({ ok: true, json: async () => contracts.generated_workload }));
  expect(screen.getByLabelText('Memory references')).toHaveValue('7, 7');
});
