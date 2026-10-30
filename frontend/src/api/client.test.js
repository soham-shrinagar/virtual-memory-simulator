import { afterEach, describe, expect, it, vi } from 'vitest';
import contracts from '../test/fixtures/contracts.json';
import {
  ApiError, compareAlgorithms, exportExperiment, importExperiment,
  simulateExperiment, validateComparison, validateSimulation,
} from './client.js';

afterEach(() => vi.unstubAllGlobals());
const clone = (value) => JSON.parse(JSON.stringify(value));
const respond = (data) => vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => data }));

describe('Python / JavaScript contract', () => {
  it.each(contracts.simulations)('accepts the real $policy trace including offsets and policy state', (response) => {
    expect(validateSimulation(response)).toBe(response);
    expect(response.events[1].offset).toBe(1);
  });

  it('accepts the complete real comparison matrix', () => {
    expect(validateComparison(contracts.comparison)).toBe(contracts.comparison);
  });

  it.each([
    (data) => { data.config.page_size = 1000; },
    (data) => { data.events[1].physical_address += 1; },
    (data) => { data.metrics.faults += 1; },
    (data) => { data.events[0].state.policy_state.order = [31]; },
    (data) => { data.initial_state.frames[0].page = 0; },
    (data) => { data.events[0].state.metrics.hit_rate = Infinity; },
    (data) => { data.events.pop(); },
  ])('rejects a corrupted simulation contract', (corrupt) => {
    const response = clone(contracts.simulations[0]);
    corrupt(response);
    expect(() => validateSimulation(response)).toThrow(/Unexpected/);
  });

  it('rejects duplicate comparison rows', () => {
    const response = clone(contracts.comparison);
    response.rows[1] = response.rows[0];
    expect(() => validateComparison(response)).toThrow(/Unexpected/);
  });

  it('posts relative URLs with the supplied cancellation signal', async () => {
    respond(contracts.simulations[0]);
    const controller = new AbortController();
    const request = { workload: [0, 4097, 0, 8194], input_mode: 'addresses', policy: 'fifo' };
    expect(await simulateExperiment(request, controller.signal)).toEqual(contracts.simulations[0]);
    expect(fetch).toHaveBeenCalledWith('/api/simulate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request), signal: controller.signal,
    });
  });

  it('reads validated comparison responses', async () => {
    respond(contracts.comparison);
    expect(await compareAlgorithms({ workload: [0] })).toEqual(contracts.comparison);
    expect(fetch.mock.calls[0][0]).toBe('/api/compare');
  });

  it('round-trips versioned experiment data through both routes', async () => {
    respond(contracts.experiment);
    const exported = await exportExperiment({ workload: '0 4097 0 8194', input_mode: 'addresses' });
    expect(await importExperiment(exported)).toEqual(contracts.experiment);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/experiments/export', '/api/experiments/import']);
  });

  it('sends original JSON file text so the server can reject duplicate keys', async () => {
    respond(contracts.experiment);
    const text = '{"policy":"lru","policy":"fifo"}';
    await importExperiment(text);
    expect(fetch.mock.calls[0][1].body).toBe(text);
  });

  it('exposes field and reference information for validation failures', async () => {
    const errors = [{ field: 'workload', message: 'Out of range.', token_index: 3 }];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ errors }) }));
    await expect(simulateExperiment({ workload: [99] })).rejects.toMatchObject({
      name: 'ApiError', status: 422, errors, message: 'workload (reference 3): Out of range.',
    });
    expect(ApiError.prototype).toBeInstanceOf(Error);
  });

  it('preserves cancellation instead of turning it into a contract error', async () => {
    const cancellation = new DOMException('Aborted', 'AbortError');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(cancellation));
    await expect(simulateExperiment({ workload: [0] })).rejects.toBe(cancellation);
  });
});
