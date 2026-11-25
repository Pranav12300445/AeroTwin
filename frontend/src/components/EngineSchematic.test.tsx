import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EngineSchematic from './EngineSchematic'
import { telemetry, faulty } from '@/test-utils'

const GREEN = '#22c55e', RED = '#ef4444'
const strokeOf = (label: string) =>
  screen.getByText(label).closest('svg')!.querySelectorAll('rect[stroke]')

describe('EngineSchematic', () => {
  it('renders placeholders with no data', () => {
    render(<EngineSchematic latest={null} />)
    expect(screen.getByText('NORMAL')).toBeInTheDocument()
    expect(screen.getByText('—°C')).toBeInTheDocument()
  })

  it('shows live EGT and N1 readings', () => {
    render(<EngineSchematic latest={telemetry({ egt: 641.4, rpm_n1: 73500 })} />)
    expect(screen.getByText('641°C')).toBeInTheDocument()
    expect(screen.getByText('73.5k')).toBeInTheDocument()
  })

  it('all zones are green when healthy', () => {
    render(<EngineSchematic latest={telemetry()} />)
    const strokes = Array.from(strokeOf('COMPRESSOR')).map(r => r.getAttribute('stroke'))
    expect(strokes.every(s => s === GREEN)).toBe(true)
    expect(screen.queryByText(/WEAR|CLOGGED/)).not.toBeInTheDocument()
  })

  it('highlights the compressor on a stall', () => {
    render(<EngineSchematic latest={faulty('compressor_stall')} />)
    expect(screen.getByText('COMPRESSOR')).toHaveAttribute('fill', RED)
    expect(screen.getByText('TURBINE')).toHaveAttribute('fill', GREEN)
  })

  it('flags both bearings on bearing wear', () => {
    render(<EngineSchematic latest={faulty('bearing_wear')} />)
    expect(screen.getAllByText(/WEAR/)).toHaveLength(2)
  })

  it('flags the combustor on a clogged nozzle', () => {
    render(<EngineSchematic latest={faulty('fuel_nozzle_clog')} />)
    expect(screen.getByText(/CLOGGED/)).toBeInTheDocument()
    expect(screen.getByText('COMBUSTOR')).toHaveAttribute('fill', RED)
  })

  it('shows the engine status label', () => {
    render(<EngineSchematic latest={telemetry({ engine_status: 'warning' })} />)
    expect(screen.getByText('WARNING')).toBeInTheDocument()
  })
})
