import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StrictMode } from 'react';
import App from './App.jsx';

const health = { status: 'ok', application: 'vmsim', version: '0.1.0', frontend_ready: true };
afterEach(() => vi.unstubAllGlobals());

describe('foundation connection', () => {
  it('checks the relative API and shows the connected backend in Strict Mode', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => health });
    vi.stubGlobal('fetch', fetcher);
    render(<StrictMode><App /></StrictMode>);
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledWith('/api/health', expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Virtual memory');
  });

  it('reports a failed connection and recovers on retry', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ ok: true, json: async () => health });
    vi.stubGlobal('fetch', fetcher);
    render(<App />);
    expect(await screen.findByText('Offline')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /check connection/i }));
    expect(await screen.findByText('Connected')).toBeInTheDocument();
  });

  it('rejects an unexpected API contract', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));
    render(<App />);
    await waitFor(() => expect(screen.getByText('Offline')).toBeInTheDocument());
  });
});
