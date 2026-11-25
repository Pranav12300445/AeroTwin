import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import AgentActivityLog from './AgentActivityLog'

const evt = (i: number, agent = 'telemetry_monitor') =>
  ({ timestamp: '2026-11-23T09:00:00Z', agent, event: 'x', summary: `event ${i}` })

describe('AgentActivityLog', () => {
  it('shows a waiting message when empty', () => {
    render(<AgentActivityLog events={[]} />)
    expect(screen.getByText(/Waiting for agent events/)).toBeInTheDocument()
  })

  it('shows newest first, at most 30', () => {
    render(<AgentActivityLog events={Array.from({ length: 40 }, (_, i) => evt(i))} />)
    const rows = screen.getAllByText(/^event \d+$/)
    expect(rows).toHaveLength(30)
    expect(rows[0]).toHaveTextContent('event 39')
    expect(rows[29]).toHaveTextContent('event 10')
  })

  it('formats agent names and tolerates unknown agents', () => {
    render(<AgentActivityLog events={[evt(1, 'maintenance_planner'), evt(2, 'brand_new_agent')]} />)
    expect(screen.getByText('maintenance planner')).toBeInTheDocument()
    expect(screen.getByText('brand new agent')).toBeInTheDocument()
  })
})
