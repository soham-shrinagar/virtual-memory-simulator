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

