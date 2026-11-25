import { describe, it, expect, vi, beforeEach } from 'vitest'
import { login, fetchWithAuth, injectFault, resetSimulator, createTelemetrySocket } from './api'

const fetchMock = vi.fn()
const json = (body: unknown, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  localStorage.clear()
})

describe('login', () => {
  it('posts form-encoded credentials and returns the token payload', async () => {
    fetchMock.mockReturnValue(json({ access_token: 't', role: 'admin' }))
    const data = await login('admin', 'admin123')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://localhost:8000/api/auth/login')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/x-www-form-urlencoded')
    expect(new URLSearchParams(init.body).get('username')).toBe('admin')
    expect(new URLSearchParams(init.body).get('password')).toBe('admin123')
    expect(data).toEqual({ access_token: 't', role: 'admin' })
  })

  it('throws on bad credentials', async () => {
    fetchMock.mockReturnValue(json({ detail: 'Invalid credentials' }, 401))
    await expect(login('a', 'b')).rejects.toThrow('Login failed')
  })
})

describe('fetchWithAuth', () => {
  it('sends the stored bearer token', async () => {
    localStorage.setItem('token', 'abc')
    fetchMock.mockReturnValue(json({ ok: 1 }))
    expect(await fetchWithAuth('/api/x')).toEqual({ ok: 1 })
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer abc')
  })

  it('throws the server detail on 403 (e.g. operator injecting a fault)', async () => {
    localStorage.setItem('token', 'abc')
    fetchMock.mockReturnValue(json({ detail: 'Insufficient permissions' }, 403))
    await expect(fetchWithAuth('/api/x')).rejects.toThrow('Insufficient permissions')
  })

  it('falls back to a generic message when the error body is not JSON', async () => {
    fetchMock.mockReturnValue(Promise.resolve({ ok: false, status: 500, json: () => Promise.reject(new Error('x')) }))
    await expect(fetchWithAuth('/api/x')).rejects.toThrow('Request failed (500)')
  })

  it('clears the token and redirects to login on 401', async () => {
    localStorage.setItem('token', 'expired')
    const loc = { href: '/dashboard' }
    vi.stubGlobal('location', loc)
    fetchMock.mockReturnValue(json({}, 401))
    await expect(fetchWithAuth('/api/x')).rejects.toThrow('Unauthorized')
    expect(localStorage.getItem('token')).toBeNull()
    expect(loc.href).toBe('/')
  })
})

describe('simulator control', () => {
  it('injectFault POSTs to the scenario endpoint', async () => {
    fetchMock.mockReturnValue(json({ status: 'ok' }))
    await injectFault('bearing_wear')
    expect(fetchMock.mock.calls[0][0]).toContain('/api/simulator/fault/bearing_wear')
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
  })

  it('resetSimulator POSTs to /reset', async () => {
    fetchMock.mockReturnValue(json({ status: 'ok' }))
    await resetSimulator()
    expect(fetchMock.mock.calls[0][0]).toContain('/api/simulator/reset')
  })
})

describe('createTelemetrySocket', () => {
  it('passes the JWT as a query parameter (the server requires it)', () => {
    const urls: string[] = []
    vi.stubGlobal('WebSocket', class { constructor(u: string) { urls.push(u) } })
    localStorage.setItem('token', 'a b+c')
    createTelemetrySocket()
    expect(urls[0]).toBe('ws://localhost:8000/ws/telemetry?token=a%20b%2Bc')
  })

  it('connects with an empty token when logged out (server will refuse)', () => {
    const urls: string[] = []
    vi.stubGlobal('WebSocket', class { constructor(u: string) { urls.push(u) } })
    createTelemetrySocket()
    expect(urls[0]).toMatch(/\?token=$/)
  })
})
