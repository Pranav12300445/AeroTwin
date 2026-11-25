import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import FaultTimeline from './FaultTimeline'
import { telemetry, faulty } from '@/test-utils'

describe('FaultTimeline', () => {
  it('handles no data', () => {
    render(<FaultTimeline latest={null} history={[]} />)
    expect(screen.getByText(/No fault events yet/)).toBeInTheDocument()
  })

  it('healthy: status, score, twin health and no faults', () => {
    render(<FaultTimeline latest={telemetry({ twin_health_factor: 0.987, twin_residual: -3.21 })} history={[telemetry()]} />)
    expect(screen.getByText('NORMAL')).toBeInTheDocument()
    expect(screen.getByText('No faults detected')).toBeInTheDocument()
    expect(screen.getByText('98.7%')).toBeInTheDocument()
    expect(screen.getByText('-3.2°C')).toBeInTheDocument()
    expect(screen.queryByText(/Drift Detected/)).not.toBeInTheDocument()
  })

  it('faulty: fault name, RUL and anomaly score', () => {
    const f = faulty('fuel_nozzle_clog', { rul_hours: 41.26, anomaly_score: 0.853 })
    render(<FaultTimeline latest={f} history={[f]} />)
    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
    expect(screen.getAllByText('Fuel Nozzle Clog').length).toBeGreaterThan(0)
    expect(screen.getByText(/Anomaly Score: 85.3%/)).toBeInTheDocument()
    expect(screen.getAllByText(/41\.3h/).length).toBeGreaterThan(0)
  })

  it('omits RUL when it is null', () => {
    const f = faulty('bearing_wear', { rul_hours: null })
    render(<FaultTimeline latest={f} history={[f]} />)
    expect(screen.queryByText('RUL')).not.toBeInTheDocument()
  })

  it('shows the drift warning', () => {
    render(<FaultTimeline latest={telemetry({ twin_drift_detected: true })} history={[]} />)
    expect(screen.getByText(/Drift Detected/)).toBeInTheDocument()
  })

  it('history lists only fault samples, last 10, newest first', () => {
    const hist = [telemetry(), ...Array.from({ length: 12 }, (_, i) => faulty('bearing_wear', { rul_hours: 100 - i }))]
    render(<FaultTimeline latest={hist.at(-1)!} history={hist} />)
    const rows = screen.getAllByText(/RUL: \d+\.\dh/)
    expect(rows).toHaveLength(10)
    expect(rows[0]).toHaveTextContent('RUL: 89.0h')
    expect(rows[9]).toHaveTextContent('RUL: 98.0h')
  })
})
