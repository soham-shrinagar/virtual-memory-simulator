export interface HealthResponse {
  status: 'ok';
  application: 'vmsim';
  version: string;
  phase: 0;
  frontend_ready: boolean;
}

export async function getHealth(signal: AbortSignal): Promise<HealthResponse> {
  const response = await fetch('/api/health', { signal });
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (
    typeof data !== 'object' || data === null ||
    !('status' in data) || data.status !== 'ok' ||
    !('application' in data) || data.application !== 'vmsim' ||
    !('version' in data) || typeof data.version !== 'string' ||
    !('phase' in data) || data.phase !== 0 ||
    !('frontend_ready' in data) || typeof data.frontend_ready !== 'boolean'
  ) throw new Error('Unexpected backend response');
  return data as HealthResponse;
}

