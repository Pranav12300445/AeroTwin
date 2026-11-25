import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AlertToast from './AlertToast'
import { telemetry, faulty } from '@/test-utils'

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
afterEach(() => vi.useRealTimers())

describe('AlertToast', () => {
  it('renders nothing without data or alerts', () => {
    const { container, rerender } = render(<AlertToast latest={null} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<AlertToast latest={telemetry()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('toasts on the false->true anomaly transition and on a new fault', () => {
    const { rerender } = render(<AlertToast latest={telemetry()} />)
    rerender(<AlertToast latest={faulty('bearing_wear', { rul_hours: 12.46 })} />)
    expect(screen.getByText(/Anomaly detected! vibration \(score: 90.0%\)/)).toBeInTheDocument()
    expect(screen.getByText(/Fault: Bearing Wear — RUL: 12.5h/)).toBeInTheDocument()
  })

  it('does not repeat the same alert on every tick', () => {
    const { rerender } = render(<AlertToast latest={telemetry()} />)
    for (let i = 0; i < 5; i++) rerender(<AlertToast latest={faulty('bearing_wear', { timestamp: String(i) })} />)
    expect(screen.getAllByText(/Anomaly detected/)).toHaveLength(1)
    expect(screen.getAllByText(/Fault: Bearing Wear/)).toHaveLength(1)
  })

  it('toasts again when the fault type changes', () => {
    const { rerender } = render(<AlertToast latest={telemetry()} />)
    rerender(<AlertToast latest={faulty('bearing_wear')} />)
    rerender(<AlertToast latest={faulty('compressor_stall')} />)
    expect(screen.getByText(/Fault: Compressor Stall/)).toBeInTheDocument()
  })

  it('shows "returned to normal" when a fault clears', () => {
    const { rerender } = render(<AlertToast latest={telemetry()} />)
    rerender(<AlertToast latest={faulty('bearing_wear')} />)
    rerender(<AlertToast latest={telemetry()} />)
    expect(screen.getByText(/returned to normal/)).toBeInTheDocument()
  })

  it('uses "?" when RUL is unknown', () => {
    const { rerender } = render(<AlertToast latest={telemetry()} />)
    rerender(<AlertToast latest={faulty('bearing_wear', { rul_hours: null })} />)
    expect(screen.getByText(/RUL: \?h/)).toBeInTheDocument()
  })

  it('can be dismissed manually', async () => {
    const { rerender } = render(<AlertToast latest={telemetry()} />)
    rerender(<AlertToast latest={faulty('bearing_wear')} />)
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const buttons = screen.getAllByRole('button')
    await user.click(buttons[0])
    expect(screen.getAllByRole('button')).toHaveLength(buttons.length - 1)
  })

  it('auto-dismisses after 6 seconds', () => {
    const { rerender, container } = render(<AlertToast latest={telemetry()} />)
    rerender(<AlertToast latest={faulty('bearing_wear')} />)
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0)
    act(() => { vi.advanceTimersByTime(6000) })
    act(() => { vi.advanceTimersByTime(6000) })
    expect(container).toBeEmptyDOMElement()
  })

  it('keeps at most 5 toasts', () => {
    const { rerender } = render(<AlertToast latest={telemetry()} />)
    const kinds = ['bearing_wear', 'compressor_stall', 'fuel_nozzle_clog', 'turbine_erosion']
    kinds.forEach(k => rerender(<AlertToast latest={faulty(k)} />))
    expect(screen.getAllByRole('button').length).toBeLessThanOrEqual(5)
  })
})
