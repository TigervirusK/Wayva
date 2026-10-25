export interface HealthResponse {
  status: 'ok'
  service: string
  database: 'connected'
  version: string
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

export async function getHealth(signal: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBase}/health`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(`Connection check failed (${response.status}).`)
  const data: unknown = await response.json()
  if (
    typeof data !== 'object' || data === null ||
    !('status' in data) || data.status !== 'ok' ||
    !('database' in data) || data.database !== 'connected' ||
    !('service' in data) || typeof data.service !== 'string' ||
    !('version' in data) || typeof data.version !== 'string'
  ) {
    throw new Error('The server returned an unexpected health response.')
  }
  return data as HealthResponse
}
