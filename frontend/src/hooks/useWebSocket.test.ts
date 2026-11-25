import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useWebSocket } from './useWebSocket'
import { telemetry, faulty } from '@/test-utils'

class MockSocket {
  static instances: MockSocket[] = []
  static OPEN = 1
  readyState = 1
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor(public url: string) { MockSocket.instances.push(this) }
  send(d: string) { this.sent.push(d) }
  close() { this.closed = true; this.onclose?.() }
}

const last = () => MockSocket.instances[MockSocket.instances.length - 1]
const push = (type: string, data: unknown) =>
  act(() => { last().onmessage!({ data: JSON.stringify({ type, data }) }) })

beforeEach(() => {
  MockSocket.instances = []
  vi.stubGlobal('WebSocket', MockSocket)
  localStorage.setItem('token', 'tok')
  vi.useFakeTimers()
})
afterEach(() => vi.useRealTimers())

describe('useWebSocket', () => {
  it('connects with the stored token and reports connected on open', () => {
    const { result } = renderHook(() => useWebSocket())
    expect(last().url).toContain('/ws/telemetry?token=tok')
    expect(result.current.connected).toBe(false)
    act(() => last().onopen!())
    expect(result.current.connected).toBe(true)
  })

  it('stores latest telemetry and keeps at most 120 history samples', () => {
    const { result } = renderHook(() => useWebSocket())
    for (let i = 0; i < 130; i++) push('telemetry', telemetry({ egt: 600 + i }))
    expect(result.current.latest!.egt).toBe(729)
    expect(result.current.history).toHaveLength(120)
    expect(result.current.history[0].egt).toBe(610)
  })

  it('logs anomaly and fault events from telemetry', () => {
    const { result } = renderHook(() => useWebSocket())
    push('telemetry', faulty('bearing_wear'))
    const events = result.current.agentEvents.map(e => e.event)
    expect(events).toEqual(['anomaly.detected', 'fault.predicted'])
    expect(result.current.agentEvents[1].summary).toBe('bearing wear — RUL: 12.5h')
  })

  it('normal telemetry adds no agent events', () => {
    const { result } = renderHook(() => useWebSocket())
    push('telemetry', telemetry())
    expect(result.current.agentEvents).toEqual([])
  })

  it('stores maintenance recommendations and clears them when the engine is normal again', () => {
    const { result } = renderHook(() => useWebSocket())
    const rec = { fault_type: 'bearing_wear', priority: 'urgent', message: 'Inspect bearings', steps: [] }
    push('maintenance', rec)
    expect(result.current.maintenance).toMatchObject({ fault_type: 'bearing_wear' })
    expect(result.current.agentEvents.at(-1)).toMatchObject({ agent: 'maintenance_planner', summary: 'Inspect bearings' })
    push('telemetry', faulty('bearing_wear'))
    expect(result.current.maintenance).not.toBeNull()
    push('telemetry', telemetry())
    expect(result.current.maintenance).toBeNull()
  })

  it('maps agent_activity messages, with defaults for missing fields', () => {
    const { result } = renderHook(() => useWebSocket())
    push('agent_activity', { agent: 'api', event: 'simulator.command', summary: 'inject', timestamp: 't1' })
    push('agent_activity', {})
    expect(result.current.agentEvents[0]).toEqual({ timestamp: 't1', agent: 'api', event: 'simulator.command', summary: 'inject' })
    expect(result.current.agentEvents[1]).toMatchObject({ agent: 'system', event: 'activity', summary: '' })
  })

  it('caps the agent event log at 100', () => {
    const { result } = renderHook(() => useWebSocket())
    for (let i = 0; i < 150; i++) push('agent_activity', { agent: 'api', summary: String(i) })
    expect(result.current.agentEvents).toHaveLength(100)
    expect(result.current.agentEvents.at(-1)!.summary).toBe('149')
  })

  it('ignores malformed frames and unknown types', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => last().onmessage!({ data: 'not json' }))
    push('mystery', {})
    expect(result.current.latest).toBeNull()
  })

  it('reconnects 3 s after the socket closes', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => last().onopen!())
    act(() => last().onclose!())
    expect(result.current.connected).toBe(false)
    expect(MockSocket.instances).toHaveLength(1)
    act(() => { vi.advanceTimersByTime(3000) })
    expect(MockSocket.instances).toHaveLength(2)
  })

  it('closes the socket on error (which triggers the reconnect path)', () => {
    renderHook(() => useWebSocket())
    const s = last()
    act(() => s.onerror!())
    expect(s.closed).toBe(true)
  })

  it('sendCommand sends JSON only while the socket is open', () => {
    const { result } = renderHook(() => useWebSocket())
    act(() => result.current.sendCommand('inject_fault', 'compressor_stall'))
    expect(JSON.parse(last().sent[0])).toEqual({ action: 'inject_fault', scenario: 'compressor_stall' })
    last().readyState = 0
    act(() => result.current.sendCommand('inject_fault', 'x'))
    expect(last().sent).toHaveLength(1)
  })

  it('closes the socket and stops reconnecting on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket())
    const s = last()
    unmount()
    expect(s.closed).toBe(true)
    act(() => { vi.advanceTimersByTime(10000) })
    expect(MockSocket.instances).toHaveLength(1)
  })
})
