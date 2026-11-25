import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { telemetry, faulty } from '@/test-utils'

const push = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))

const api = vi.hoisted(() => ({ injectFault: vi.fn(), resetSimulator: vi.fn() }))
vi.mock('@/lib/api', () => api)

const ws = vi.hoisted(() => ({ state: {} as any }))
vi.mock('@/hooks/useWebSocket', () => ({ useWebSocket: () => ws.state }))

// recharts is irrelevant here and heavy; the real components have their own tests
vi.mock('@/components/TelemetryCharts', () => ({ default: () => <div data-testid="charts" /> }))

import DashboardPage from './page'

const b64 = (o: object) => btoa(JSON.stringify(o))
const jwt = (sub: string) => `h.${b64({ sub })}.s`

function setup(role: string | null, state: Partial<any> = {}) {
  if (role) { localStorage.setItem('token', jwt(role)); localStorage.setItem('role', role) }
  ws.state = { connected: true, latest: telemetry(), history: [], agentEvents: [], maintenance: null,
               sendCommand: vi.fn(), ...state }
  return render(<DashboardPage />)
}

beforeEach(() => {
  push.mockReset(); api.injectFault.mockReset(); api.resetSimulator.mockReset(); localStorage.clear()
})

describe('DashboardPage: session', () => {
  it('redirects to the login page without a token', async () => {
    setup(null)
    await waitFor(() => expect(push).toHaveBeenCalledWith('/'))
  })

  it('shows the username decoded from the JWT and the role badge', async () => {
    setup('admin')
    expect(await screen.findByText('admin', { selector: 'span.text-xs' })).toBeInTheDocument()
    expect(screen.getByText('⚙️ Admin')).toBeInTheDocument()
  })

  it('survives a malformed token', async () => {
    localStorage.setItem('token', 'not-a-jwt'); localStorage.setItem('role', 'operator')
    ws.state = { connected: true, latest: null, history: [], agentEvents: [], maintenance: null, sendCommand: vi.fn() }
    render(<DashboardPage />)
    expect(await screen.findByText('Logout')).toBeInTheDocument()
  })

  it('logout clears the session and returns to login', async () => {
    setup('operator')
    await userEvent.click(screen.getByText('Logout'))
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('role')).toBeNull()
    expect(push).toHaveBeenCalledWith('/')
  })
})

describe('DashboardPage: header status', () => {
  it('shows connection state', () => {
    setup('admin', { connected: false })
    expect(screen.getByText('Connecting...')).toBeInTheDocument()
  })

  it.each([['normal', 'NORMAL'], ['warning', 'WARNING'], ['critical', 'CRITICAL']])(
    'engine status %s is shown', (status, label) => {
      setup('admin', { latest: telemetry({ engine_status: status as any }) })
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    })
})

describe('DashboardPage: role-based views', () => {
  it('operator: read-only. Summary only, no controls, no agent log', async () => {
    setup('operator')
    expect(await screen.findByText(/No maintenance required/)).toBeInTheDocument()
    expect(screen.queryByText(/Reset Normal/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Agent Activity/i)).not.toBeInTheDocument()
  })

  it('operator sees only "action required" (no procedure details) during a fault', async () => {
    setup('operator', { latest: faulty('bearing_wear') })
    expect(await screen.findByText(/Maintenance action required/)).toBeInTheDocument()
    expect(screen.queryByText('Bearing Inspection & Replacement')).not.toBeInTheDocument()
  })

  it.each(['maintenance_engineer', 'admin'])('%s: full maintenance details, controls, agent log', async (role) => {
    setup(role, { latest: faulty('bearing_wear'),
                  agentEvents: [{ timestamp: 't', agent: 'maintenance_planner', event: 'e', summary: 'planned' }] })
    expect(await screen.findByText('Bearing Inspection & Replacement')).toBeInTheDocument()
    expect(screen.getByText(/Reset Normal/)).toBeInTheDocument()
    expect(screen.getByText('planned')).toBeInTheDocument()
  })
})

describe('DashboardPage: controls', () => {
  it('inject fault calls the REST API', async () => {
    setup('admin')
    await userEvent.click(await screen.findByText(/Compressor Stall/))
    expect(api.injectFault).toHaveBeenCalledWith('compressor_stall')
  })

  it('falls back to the WebSocket command if the REST call fails', async () => {
    api.injectFault.mockRejectedValue(new Error('network'))
    const sendCommand = vi.fn()
    setup('admin', { sendCommand })
    await userEvent.click(await screen.findByText(/Bearing Wear/))
    await waitFor(() => expect(sendCommand).toHaveBeenCalledWith('inject_fault', 'bearing_wear'))
  })

  it('reset calls the REST API, with a WebSocket fallback', async () => {
    const sendCommand = vi.fn()
    setup('admin', { sendCommand })
    await userEvent.click(await screen.findByText(/Reset Normal/))
    expect(api.resetSimulator).toHaveBeenCalled()

    api.resetSimulator.mockRejectedValue(new Error('x'))
    await userEvent.click(screen.getByText(/Reset Normal/))
    await waitFor(() => expect(sendCommand).toHaveBeenCalledWith('inject_fault', 'none'))
  })
})
