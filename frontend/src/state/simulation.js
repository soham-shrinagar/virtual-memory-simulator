export const defaultDraft = {
  pageSize: '4096', virtualPages: '8', physicalFrames: '3',
  inputMode: 'pages', policy: 'fifo', workload: '1, 2, 3, 1, 4, 2, 5',
};

export const initialState = { draft: defaultDraft, trace: null, status: 'idle', error: null };

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
    case 'START':
      return { ...state, trace: null, status: 'loading', error: null };
    case 'SUCCESS':
      return { ...state, trace: action.trace, status: 'ready', error: null };
    case 'FAIL':
      return { ...state, trace: null, status: 'error', error: action.message };
    case 'CANCEL':
      return { ...state, trace: null, status: 'idle', error: null };
    default:
      return state;
  }
}

export function buildRequest(draft) {
  const integer = (value, name, min, max) => {
    if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) < min || Number(value) > max) {
      throw new Error(`${name} must be an integer from ${min} to ${max}.`);
    }
    return Number(value);
  };
  const pageSize = integer(draft.pageSize, 'Page size', 256, 65536);
  if ((pageSize & (pageSize - 1)) !== 0) throw new Error('Page size must be a power of two.');
  const virtualPages = integer(draft.virtualPages, 'Virtual pages', 1, 256);
  const physicalFrames = integer(draft.physicalFrames, 'Physical frames', 1, 32);
  if (!draft.workload.trim()) throw new Error('Enter at least one memory reference.');
  return {
    config: { page_size: pageSize, virtual_pages: virtualPages, physical_frames: physicalFrames },
    workload: draft.workload, input_mode: draft.inputMode, policy: draft.policy,
  };
}

export function formatBytes(bytes) {
  return `${(bytes / 1024).toLocaleString('en-US', { maximumFractionDigits: 2 })} KiB`;
}
