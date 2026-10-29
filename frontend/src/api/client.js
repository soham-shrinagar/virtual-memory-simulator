export async function getHealth(signal) {
  const response = await fetch('/api/health', { signal });
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
  const data = await response.json();
  if (
    typeof data !== 'object' || data === null ||
    !('status' in data) || data.status !== 'ok' ||
    !('application' in data) || data.application !== 'vmsim' ||
    !('version' in data) || typeof data.version !== 'string' ||
    !('phase' in data) || !Number.isInteger(data.phase) || data.phase < 0 || data.phase > 7 ||
    !('frontend_ready' in data) || typeof data.frontend_ready !== 'boolean'
  ) throw new Error('Unexpected backend response');
  return data;
}

const policies = ['fifo', 'lru', 'optimal'];
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const integer = (value, min = 0, max = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(value) && value >= min && value <= max;
const unique = (values) => new Set(values).size === values.length;
const requireContract = (condition, name) => {
  if (!condition) throw new Error(`Unexpected ${name} response`);
};

export class ApiError extends Error {
  constructor(message, status, errors) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errors = errors;
  }
}

async function postJson(path, body, signal) {
  const response = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  const data = await response.json();
  if (!response.ok) {
    const errors = Array.isArray(data?.errors) ? data.errors : [];
    const message = errors.map((error) => `${error.field}${error.token_index ? ` (reference ${error.token_index})` : ''}: ${error.message}`).join('; ');
    throw new ApiError(message || `Server returned HTTP ${response.status}`, response.status, errors);
  }
  return data;
}

function validConfig(config) {
  return object(config) && integer(config.page_size, 256, 65536) &&
    (config.page_size & (config.page_size - 1)) === 0 &&
    integer(config.virtual_pages, 1, 256) && integer(config.physical_frames, 1, 32);
}

function validMetrics(metrics, references) {
  if (!object(metrics) || !integer(metrics.hits) || !integer(metrics.faults) || !integer(metrics.replacements) ||
      metrics.references !== references || metrics.hits + metrics.faults !== references || metrics.replacements > metrics.faults) return false;
  if (references === 0) return metrics.hit_rate === null && metrics.fault_rate === null;
  return Number.isFinite(metrics.hit_rate) && Number.isFinite(metrics.fault_rate) &&
    Math.abs(metrics.hit_rate - metrics.hits / references) < 1e-12 &&
    Math.abs(metrics.fault_rate - metrics.faults / references) < 1e-12;
}

function validWorkload(data) {
  if (!object(data) || data.schema_version !== 1 || !validConfig(data.config) ||
      !['pages', 'addresses'].includes(data.input_mode) || !Array.isArray(data.workload) ||
      data.workload.length < 1 || data.workload.length > 1000) return false;
  const upper = data.input_mode === 'pages' ? data.config.virtual_pages : data.config.page_size * data.config.virtual_pages;
  return data.workload.every((value) => integer(value, 0, upper - 1));
}

function validDerivedConfig(config) {
  return config.virtual_capacity === config.virtual_pages * config.page_size &&
    config.physical_capacity === config.physical_frames * config.page_size && config.offset_bits === Math.log2(config.page_size);
}

function validSnapshot(state, config, policy, step) {
  if (!object(state) || state.step !== step || !validMetrics(state.metrics, step) ||
      !Array.isArray(state.frames) || state.frames.length !== config.physical_frames) return false;
  if (!state.frames.every((frame, index) => object(frame) && frame.frame_id === index &&
      (frame.page === null || integer(frame.page, 0, config.virtual_pages - 1)))) return false;
  const occupied = state.frames.filter((frame) => frame.page !== null);
  const ids = occupied.map((frame) => frame.frame_id);
  if (!unique(occupied.map((frame) => frame.page)) || state.metrics.faults - state.metrics.replacements !== occupied.length ||
      !Array.isArray(state.resident_pages) || state.resident_pages.length !== occupied.length ||
      !state.resident_pages.every((entry) => object(entry) && integer(entry.frame_id, 0, config.physical_frames - 1) &&
        entry.page !== null && state.frames[entry.frame_id].page === entry.page) ||
      !unique(state.resident_pages.map((entry) => entry.page))) return false;
  const metadata = state.policy_state;
  if (!object(metadata) || metadata.name !== policy || !Array.isArray(metadata.order) ||
      !Array.isArray(metadata.last_access) || !Array.isArray(metadata.next_use)) return false;
  const validPositions = (positions, future) => positions.length === ids.length && unique(positions.map((entry) => entry?.frame_id)) &&
    positions.every((entry) => object(entry) && ids.includes(entry.frame_id) &&
      (future ? entry.step === null || integer(entry.step, step + 1, 1000) : integer(entry.step, 1, step)));
  if (policy === 'optimal') return metadata.order.length === 0 && metadata.last_access.length === 0 && validPositions(metadata.next_use, true);
  if (metadata.order.length !== ids.length || !unique(metadata.order) || !metadata.order.every((id) => ids.includes(id)) || metadata.next_use.length !== 0) return false;
  return policy === 'fifo' ? metadata.last_access.length === 0 : validPositions(metadata.last_access, false);
}

export function validateSimulation(data) {
  requireContract(validWorkload(data) && policies.includes(data.policy) && validDerivedConfig(data.config), 'simulation');
  requireContract(validSnapshot(data.initial_state, data.config, data.policy, 0) &&
    Array.isArray(data.events) && data.events.length === data.workload.length, 'simulation');
  let previous = data.initial_state;
  data.events.forEach((event, index) => {
    const config = data.config;
    const value = data.workload[index];
    const address = data.input_mode === 'pages' ? value * config.page_size : value;
    const page = Math.floor(address / config.page_size);
    const offset = address % config.page_size;
    requireContract(object(event) && event.step === index + 1 && event.input_value === value &&
      event.virtual_address === address && event.page === page && event.offset === offset &&
      ['hit', 'fault'].includes(event.result) && integer(event.frame_id, 0, config.physical_frames - 1) &&
      (event.victim_page === null || integer(event.victim_page, 0, config.virtual_pages - 1)) &&
      typeof event.reason === 'string' && event.reason.length > 0 &&
      validSnapshot(event.state, config, data.policy, index + 1), 'simulation event');
    const hit = previous.frames.some((frame) => frame.page === page);
    requireContract(event.result === (hit ? 'hit' : 'fault') &&
      event.state.frames[event.frame_id].page === page && event.physical_address === event.frame_id * config.page_size + offset &&
      event.state.metrics.hits === previous.metrics.hits + Number(hit) &&
      event.state.metrics.faults === previous.metrics.faults + Number(!hit) &&
      event.state.metrics.replacements === previous.metrics.replacements + Number(event.victim_page !== null) &&
      (event.victim_page === null || (!hit && previous.frames[event.frame_id].page === event.victim_page)), 'simulation event');
    previous = event.state;
  });
  requireContract(validMetrics(data.metrics, data.workload.length) &&
    ['hits', 'faults', 'replacements'].every((key) => data.metrics[key] === previous.metrics[key]), 'simulation totals');
  return data;
}

export function validateComparison(data) {
  requireContract(validWorkload(data) && validDerivedConfig(data.config) && Array.isArray(data.policies) &&
    data.policies.length >= 1 && data.policies.length <= 3 && unique(data.policies) && data.policies.every((policy) => policies.includes(policy)) &&
    Array.isArray(data.frame_counts) && data.frame_counts.length >= 1 && data.frame_counts.length <= 32 && unique(data.frame_counts) &&
    data.frame_counts.every((count) => integer(count, 1, 32)) && Array.isArray(data.rows) &&
    data.rows.length === data.frame_counts.length * data.policies.length, 'comparison');
  const keys = [];
  for (const row of data.rows) {
    requireContract(object(row) && data.policies.includes(row.policy) && data.frame_counts.includes(row.physical_frames) &&
      validMetrics(row.metrics, data.workload.length) &&
      row.metrics.faults - row.metrics.replacements <= Math.min(row.physical_frames, data.config.virtual_pages), 'comparison row');
    keys.push(`${row.policy}/${row.physical_frames}`);
  }
  requireContract(unique(keys), 'comparison');
  return data;
}

function validateExperiment(data) {
  requireContract(validWorkload(data) && policies.includes(data.policy), 'experiment');
  return data;
}

export async function simulateExperiment(request, signal) {
  return validateSimulation(await postJson('/api/simulate', request, signal));
}

export async function compareAlgorithms(request, signal) {
  return validateComparison(await postJson('/api/compare', request, signal));
}

export async function exportExperiment(request, signal) {
  return validateExperiment(await postJson('/api/experiments/export', request, signal));
}

export async function importExperiment(request, signal) {
  return validateExperiment(await postJson('/api/experiments/import', request, signal));
}

