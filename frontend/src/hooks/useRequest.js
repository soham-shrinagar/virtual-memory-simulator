import { useCallback, useEffect, useRef, useState } from 'react';

// Abort and generation checks also protect against transports that finish after cancellation.
export default function useRequest() {
  const active = useRef(null);
  const generation = useRef(0);
  const [state, setState] = useState({ busy: false, error: null });
  const cancel = useCallback(() => {
    generation.current += 1;
    if (active.current) {
      clearTimeout(active.current.timer);
      active.current.controller.abort();
      active.current = null;
    }
  }, []);
  const reset = useCallback(() => { cancel(); setState({ busy: false, error: null }); }, [cancel]);
  useEffect(() => cancel, [cancel]);
  const run = async (task, success) => {
    if (active.current) return;
    const token = ++generation.current;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      if (generation.current !== token) return;
      cancel();
      setState({ busy: false, error: 'The request timed out. Try again.' });
    }, 15000);
    active.current = { controller, timer };
    setState({ busy: true, error: null });
    try {
      const result = await task(controller.signal);
      if (generation.current !== token) return;
      clearTimeout(timer);
      active.current = null;
      success(result);
      setState({ busy: false, error: null });
    } catch (error) {
      if (generation.current !== token) return;
      clearTimeout(timer);
      active.current = null;
      setState({ busy: false, error: error.message || 'Unable to complete the request.' });
    }
  };
  return { ...state, run, reset };
}
