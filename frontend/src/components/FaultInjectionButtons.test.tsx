import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FaultInjectionButtons from './FaultInjectionButtons'

describe('FaultInjectionButtons', () => {
  it('renders nothing for operators (read-only role)', () => {
    const { container } = render(<FaultInjectionButtons onInjectFault={vi.fn()} onReset={vi.fn()} role="operator" />)
    expect(container).toBeEmptyDOMElement()
  })

  it.each(['maintenance_engineer', 'admin'])('%s sees all four scenarios', (role) => {
    render(<FaultInjectionButtons onInjectFault={vi.fn()} onReset={vi.fn()} role={role} />)
    expect(screen.getAllByRole('button')).toHaveLength(4)
  })

  it('each button triggers its scenario / reset', async () => {
    const inject = vi.fn(), reset = vi.fn()
    render(<FaultInjectionButtons onInjectFault={inject} onReset={reset} role="admin" />)
    await userEvent.click(screen.getByText(/Bearing Wear/))
    await userEvent.click(screen.getByText(/Compressor Stall/))
    await userEvent.click(screen.getByText(/Fuel Nozzle Clog/))
    await userEvent.click(screen.getByText(/Reset Normal/))
    expect(inject.mock.calls.map(c => c[0])).toEqual(['bearing_wear', 'compressor_stall', 'fuel_nozzle_clog'])
    expect(reset).toHaveBeenCalledTimes(1)
  })
})
