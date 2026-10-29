import { useEffect, useReducer } from 'react';

function reducer(state, action) {
  if (action.type === 'TRACE') return { ...state, trace: action.trace, cursor: 0, playing: false };
  if (action.type === 'PAUSE') return { ...state, playing: false };
  if (action.type === 'SPEED') return { ...state, delay: action.delay };
  if (state.trace !== action.trace) return state;
  const end = state.trace?.events.length ?? 0;
  if (action.type === 'PLAY') return { ...state, playing: state.cursor < end };
  if (action.type === 'SEEK') return { ...state, cursor: Math.max(0, Math.min(end, action.cursor)), playing: false };
  if (action.type === 'TICK' && state.playing) {
    const cursor = Math.min(end, state.cursor + 1);
    return { ...state, cursor, playing: cursor < end };
  }
  return state;
}

export default function usePlayback(trace) {
  const [state, dispatch] = useReducer(reducer, { trace, cursor: 0, playing: false, delay: 800 });
  const active = state.trace === trace;
  const cursor = active ? state.cursor : 0;
  const playing = active && state.playing;
  const length = trace?.events.length ?? 0;

  useEffect(() => { dispatch({ type: 'TRACE', trace }); }, [trace]);

  useEffect(() => {
    if (!playing || cursor >= length) return;
    const timer = window.setTimeout(() => dispatch({ type: 'TICK', trace }), state.delay);
    return () => window.clearTimeout(timer);
  }, [trace, cursor, playing, length, state.delay]);

  useEffect(() => {
    const onVisibility = () => { if (document.hidden) dispatch({ type: 'PAUSE' }); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  const seek = (step) => {
    if (Number.isSafeInteger(step)) dispatch({ type: 'SEEK', trace, cursor: step });
  };
  return {
    cursor, playing, length, delay: state.delay,
    play: () => dispatch({ type: 'PLAY', trace }),
    pause: () => dispatch({ type: 'PAUSE' }),
    previous: () => seek(cursor - 1), next: () => seek(cursor + 1),
    reset: () => seek(0), seek,
    setDelay: (delay) => {
      if ([1600, 800, 400, 200].includes(delay)) dispatch({ type: 'SPEED', delay });
    },
  };
}
