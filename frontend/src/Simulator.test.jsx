import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App.jsx';
import contracts from './test/fixtures/contracts.json';

const health = { status: 'ok', application: 'vmsim', version: '0.1.0', phase: 4, frontend_ready: true };
const response = (data) => ({ ok: true, json: async () => data });
const policyTrace = (policy) => contracts.simulations.find((trace) => trace.policy === policy);
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

function mount(handler = (request) => Promise.resolve(response(policyTrace(request.policy)))) {
  const fetcher = vi.fn((url, options) => url === '/api/health'
    ? Promise.resolve(response(health)) : handler(JSON.parse(options.body), options));
  vi.stubGlobal('fetch', fetcher);
  const view = render(<App />);
  return { ...view, fetcher, requests: () => fetcher.mock.calls.filter(([url]) => url === '/api/simulate') };
}

function configure(policy = 'fifo') {
  fireEvent.change(screen.getByLabelText('Physical frames'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('Reference type'), { target: { value: 'addresses' } });
  fireEvent.change(screen.getByLabelText('Memory references'), { target: { value: '0, 4097, 0, 8194' } });
  fireEvent.change(screen.getByLabelText('Replacement policy'), { target: { value: policy } });
}

async function run() {
  fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
  await screen.findByRole('heading', { name: 'Physical memory' });
}

describe('interactive simulation', () => {
  it('steps through the real trace, restores prior states, seeks, and resets without new requests', async () => {
    const { requests } = mount();
    configure();
    await run();
    expect(JSON.parse(requests()[0][1].body)).toEqual({
      config: { page_size: 4096, virtual_pages: 8, physical_frames: 2 },
      workload: '0, 4097, 0, 8194', input_mode: 'addresses', policy: 'fifo',
    });
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByLabelText('Faults')).toHaveTextContent('0');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByTestId('frame-0')).toHaveTextContent('P0');
    expect(screen.getByLabelText('Faults')).toHaveTextContent('1');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByLabelText('Physical address')).toHaveTextContent('4,097');
    expect(screen.getByLabelText('Offset')).toHaveTextContent('1');
    expect(screen.getByTestId('frame-1')).toHaveTextContent('P1');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByLabelText('Hits')).toHaveTextContent('1');
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByTestId('frame-0')).toHaveTextContent('Replaced P0');
    expect(screen.getByLabelText('Faults')).toHaveTextContent('3');
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(screen.getByTestId('frame-0')).toHaveTextContent('P0');
    expect(screen.getByLabelText('Faults')).toHaveTextContent('2');
    fireEvent.click(screen.getByRole('button', { name: 'Go to step 1' }));
    expect(screen.getByLabelText('Faults')).toHaveTextContent('1');
    fireEvent.change(screen.getByLabelText('Simulation step'), { target: { value: '4' } });
    expect(screen.getByLabelText('Replacements')).toHaveTextContent('1');
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(screen.getByLabelText('Current step')).toHaveTextContent('0 / 4');
    expect(screen.getByTestId('frame-0')).toHaveTextContent('Empty');
    expect(screen.getByLabelText('Faults')).toHaveTextContent('0');
    expect(requests()).toHaveLength(1);
  });

  it.each(['fifo', 'lru', 'optimal'])('renders %s metadata from the selected snapshot', async (policy) => {
    mount(); configure(policy); await run();
    fireEvent.change(screen.getByLabelText('Simulation step'), { target: { value: '4' } });
    const section = screen.getByRole('region', { name: 'Policy state' });
    expect(section).toHaveTextContent(policy === 'fifo' ? 'Arrival order' : policy === 'lru' ? 'least recent' : 'Next reference');
    if (policy === 'optimal') expect(section).toHaveTextContent('Never used again');
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(section).toHaveTextContent('No resident pages.');
  });

  it('clears the active trace when configuration is edited and loads mode-appropriate examples', async () => {
    mount(); configure(); await run();
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    fireEvent.change(screen.getByLabelText('Virtual pages'), { target: { value: '16' } });
    expect(screen.queryByRole('heading', { name: 'Physical memory' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Your memory workspace' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Load example' }));
    expect(screen.getByLabelText('Memory references')).toHaveValue('4096, 8300, 4097');
    expect(screen.getByLabelText('Virtual pages')).toHaveValue(8);
  });

  it('reports local validation errors without sending a request', () => {
    const { requests } = mount();
    fireEvent.change(screen.getByLabelText('Physical frames'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Physical frames must be an integer');
    expect(requests()).toHaveLength(0);
  });

  it('preserves editor contents after a server validation error and allows recovery', async () => {
    const { requests } = mount((request) => request.workload === '0, 1, 8'
      ? Promise.resolve({ ok: false, status: 422, json: async () => ({ errors: [{ field: 'workload', token_index: 3, message: 'Out of range.' }] }) })
      : Promise.resolve(response(policyTrace('fifo'))));
    fireEvent.change(screen.getByLabelText('Memory references'), { target: { value: '0, 1, 8' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('reference 3');
    expect(screen.getByLabelText('Memory references')).toHaveValue('0, 1, 8');
    configure(); await run();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(requests()).toHaveLength(2);
  });

  it('ignores an obsolete response even if the transport does not honor cancellation', async () => {
    let finishFirst;
    let count = 0;
    const { requests } = mount((request) => ++count === 1
      ? new Promise((resolve) => { finishFirst = resolve; })
      : Promise.resolve(response(policyTrace(request.policy))));
    configure();
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    const oldSignal = requests()[0][1].signal;
    fireEvent.change(screen.getByLabelText('Replacement policy'), { target: { value: 'lru' } });
    expect(oldSignal.aborted).toBe(true);
    await run();
    await act(async () => { finishFirst(response(policyTrace('fifo'))); });
    expect(screen.getByRole('region', { name: 'Policy state' })).toHaveTextContent('LRU');
  });

  it('prevents duplicate submissions, cancels requests, and aborts on unmount', () => {
    const { requests, unmount } = mount(() => new Promise(() => {}));
    configure();
    fireEvent.submit(screen.getByRole('form', { name: 'Memory configuration' }));
    fireEvent.submit(screen.getByRole('form', { name: 'Memory configuration' }));
    expect(requests()).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Preparing trace…' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(requests()[0][1].signal.aborted).toBe(true);
    expect(screen.getByLabelText('Memory references')).toHaveValue('0, 4097, 0, 8194');
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    unmount();
    expect(requests()[1][1].signal.aborted).toBe(true);
  });

  it('times out a stalled request and preserves the draft', async () => {
    vi.useFakeTimers();
    const { requests } = mount(() => new Promise(() => {}));
    await act(async () => {});
    configure();
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    act(() => vi.advanceTimersByTime(15000));
    expect(screen.getByRole('alert')).toHaveTextContent('timed out');
    expect(requests()[0][1].signal.aborted).toBe(true);
    expect(screen.getByLabelText('Memory references')).toHaveValue('0, 4097, 0, 8194');
  });

  it('keeps a 1000-reference history bounded while allowing timeline navigation', async () => {
    const trace = JSON.parse(JSON.stringify(policyTrace('fifo')));
    const first = trace.events[0];
    trace.workload = Array(1000).fill(0);
    trace.events = Array.from({ length: 1000 }, (_, index) => {
      const step = index + 1;
      const metrics = { references: step, hits: index, faults: 1, replacements: 0, hit_rate: index / step, fault_rate: 1 / step };
      return { ...first, step, result: index ? 'hit' : 'fault', state: { ...first.state, step, metrics } };
    });
    trace.metrics = trace.events.at(-1).state.metrics;
    mount(() => Promise.resolve(response(trace))); configure(); await run();
    fireEvent.change(screen.getByLabelText('Simulation step'), { target: { value: '1000' } });
    const table = screen.getByRole('table', { name: 'Reference history' });
    expect(within(table).getAllByRole('row')).toHaveLength(13);
    expect(screen.getByLabelText('Hits')).toHaveTextContent('999');
    fireEvent.change(screen.getByLabelText('Simulation step'), { target: { value: '1' } });
    expect(screen.getByLabelText('Hits')).toHaveTextContent('0');
  });
});
