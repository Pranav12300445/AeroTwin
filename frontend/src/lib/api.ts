const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export async function login(username: string, password: string) {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)

  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  })
  if (!res.ok) throw new Error('Login failed')
  return res.json()
}

export async function fetchWithAuth(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem('token')
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
  })
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed (${res.status})`)
  }
  return res.json()
}

export async function injectFault(scenario: string) {
  return fetchWithAuth(`/api/simulator/fault/${scenario}`, { method: 'POST' })
}

export async function resetSimulator() {
  return fetchWithAuth('/api/simulator/reset', { method: 'POST' })
}

export function createTelemetrySocket(): WebSocket {
  // The server requires a valid JWT on the socket (same RBAC as the REST API)
  const token = localStorage.getItem('token') ?? ''
  return new WebSocket(`${WS_URL}/ws/telemetry?token=${encodeURIComponent(token)}`)
}
