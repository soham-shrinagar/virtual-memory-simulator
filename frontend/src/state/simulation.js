export const defaultDraft = {
  pageSize: '4096', virtualPages: '8', physicalFrames: '3',
  inputMode: 'pages', policy: 'fifo', tlbCapacity: '0', workload: '1, 2, 3, 1, 4, 2, 5',
};

export const initialState = { draft: defaultDraft, trace: null };

export function simulationReducer(state, action) {
  switch (action.type) {
    case 'LOAD':
      return { ...initialState, draft: action.draft };
    case 'EDIT':
      return { ...initialState, draft: { ...state.draft, [action.field]: action.value } };
    case 'EXAMPLE':
      return { ...initialState, draft: {
        ...defaultDraft, inputMode: state.draft.inputMode, policy: state.draft.policy,
        workload: state.draft.inputMode === 'addresses' ? '4096, 8300, 4097' : defaultDraft.workload,
      } };
    case 'BELADY':
      return { ...initialState, draft: { ...defaultDraft, workload: '1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5' } };
    case 'CLEAR_TRACE':
      return { ...state, trace: null };
    case 'SUCCESS':
      return { ...state, trace: action.trace };
    default:
      throw new Error(`Unknown simulation action: ${action.type}`);
  }
}

export function parseInteger(value, name, min, max) {
  if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) < min || Number(value) > max) {
    throw new Error(`${name} must be an integer from ${min} to ${max}.`);
  }
  return Number(value);
}

export function buildMemoryConfig(draft) {
  const pageSize = parseInteger(draft.pageSize, 'Page size', 256, 65536);
  if ((pageSize & (pageSize - 1)) !== 0) throw new Error('Page size must be a power of two.');
  return {
    page_size: pageSize,
    virtual_pages: parseInteger(draft.virtualPages, 'Virtual pages', 1, 256),
    physical_frames: parseInteger(draft.physicalFrames, 'Physical frames', 1, 32),
  };
}

export function buildRequest(draft) {
  const config = buildMemoryConfig(draft);
  const tlbCapacity = parseInteger(draft.tlbCapacity, 'TLB capacity', 0, 32);
  if (!draft.workload.trim()) throw new Error('Enter at least one memory reference.');
  return {
    config,
    workload: draft.workload, input_mode: draft.inputMode, policy: draft.policy,
    ...(tlbCapacity ? { tlb_capacity: tlbCapacity } : {}),
  };
}

export function formatBytes(bytes) {
  return `${(bytes / 1024).toLocaleString('en-US', { maximumFractionDigits: 2 })} KiB`;
}
