import { StrictMode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import contracts from '../test/fixtures/contracts.json';
import usePlayback from './usePlayback.js';

const trace = contracts.simulations[0];
const wrapper = ({ children }) => <StrictMode>{children}</StrictMode>;
beforeEach(() => vi.useFakeTimers());
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe('playback lifecycle', () => {
  it('advances once per tick in Strict Mode and stops at the final step', () => {
    const { result } = renderHook(() => usePlayback(trace), { wrapper });
    expect(result.current.cursor).toBe(0);
    act(() => result.current.play());
    expect(vi.getTimerCount()).toBe(1);
    for (let step = 1; step <= trace.events.length; step += 1) {
      act(() => vi.advanceTimersByTime(800));
      expect(result.current.cursor).toBe(step);
    }
    expect(result.current.playing).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    act(() => result.current.play());
    expect(result.current.playing).toBe(false);
  });

  it('pauses, changes speed, and stops playback on manual navigation', () => {
    const { result } = renderHook(() => usePlayback(trace));
    act(() => { result.current.setDelay(400); result.current.play(); });
    act(() => vi.advanceTimersByTime(400));
    expect(result.current.cursor).toBe(1);
    act(() => result.current.pause());
    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.cursor).toBe(1);
    act(() => result.current.play());
    act(() => result.current.next());
    expect(result.current.cursor).toBe(2);
    expect(result.current.playing).toBe(false);
    act(() => result.current.previous());
    expect(result.current.cursor).toBe(1);
    act(() => result.current.seek(100));
    expect(result.current.cursor).toBe(4);
    act(() => result.current.reset());
    expect(result.current.cursor).toBe(0);
    expect(result.current.delay).toBe(400);
    act(() => result.current.seek(-100));
    expect(result.current.cursor).toBe(0);
  });

  it('resets when a trace is replaced and cleans up on unmount', () => {
    const { result, rerender, unmount } = renderHook(({ current }) => usePlayback(current), { initialProps: { current: trace } });
    act(() => result.current.play());
    act(() => vi.advanceTimersByTime(800));
    rerender({ current: contracts.simulations[1] });
    expect(result.current.cursor).toBe(0);
    expect(result.current.playing).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    act(() => result.current.play());
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('pauses when the page becomes hidden', () => {
    const { result } = renderHook(() => usePlayback(trace));
    act(() => result.current.play());
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(result.current.playing).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('keeps an absent trace at step zero', () => {
    const { result } = renderHook(() => usePlayback(null));
    act(() => { result.current.play(); result.current.next(); });
    expect(result.current.cursor).toBe(0);
    expect(result.current.playing).toBe(false);
  });
});
