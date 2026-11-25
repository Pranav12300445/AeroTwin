import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import TelemetryCharts from './TelemetryCharts'
import { telemetry } from '@/test-utils'

const barOf = (label: string) =>
  screen.getAllByText(label)[0].closest('div.rounded-lg')!.querySelector('.h-full') as HTMLElement

describe('TelemetryCharts', () => {
  it('shows a waiting message before the first sample', () => {
    render(<TelemetryCharts history={[]} latest={null} />)
    expect(screen.getByText(/Waiting for telemetry data/)).toBeInTheDocument()
  })

  it('renders all seven gauges with values and units', () => {
    render(<TelemetryCharts history={[telemetry()]} latest={telemetry({ egt: 641.26, oil_pressure: 54.4 })} />)
    for (const label of ['EGT', 'RPM N1', 'Vibration', 'Oil Pressure', 'Fuel Flow', 'Oil Temp', 'RPM N2'])
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    expect(screen.getByText('641.3')).toBeInTheDocument()
    expect(screen.getByText('PSI')).toBeInTheDocument()
  })

  it.each([
    ['Vibration', { vibration: 0.7 }, 'bg-aero-green'],
    ['Vibration', { vibration: 2.5 }, 'bg-aero-yellow'],
    ['Vibration', { vibration: 6 }, 'bg-aero-red'],
    ['Oil Pressure', { oil_pressure: 35 }, 'bg-aero-yellow'],
    ['Oil Pressure', { oil_pressure: 25 }, 'bg-aero-red'],
    ['EGT', { egt: 760 }, 'bg-aero-yellow'],
    ['EGT', { egt: 850 }, 'bg-aero-red'],
    ['Fuel Flow', { fuel_flow: 0.2 }, 'bg-aero-yellow'],
    ['Fuel Flow', { fuel_flow: 0.1 }, 'bg-aero-red'],
    ['Oil Temp', { oil_temp: 110 }, 'bg-aero-yellow'],
    ['Oil Temp', { oil_temp: 125 }, 'bg-aero-red'],
  ])('%s gauge colour for %j is %s', (label, over, cls) => {
    render(<TelemetryCharts history={[]} latest={telemetry(over as any)} />)
    expect(barOf(label)).toHaveClass(cls)
  })

  it('gauge fill is proportional and clamped to 0-100%', () => {
    const { rerender } = render(<TelemetryCharts history={[]} latest={telemetry({ egt: 500 })} />)
    expect(barOf('EGT')).toHaveStyle({ width: '50%' })
    rerender(<TelemetryCharts history={[]} latest={telemetry({ egt: 1200 })} />)
    expect(barOf('EGT')).toHaveStyle({ width: '100%' })
  })

  it('renders four mini charts', () => {
    render(<TelemetryCharts history={[telemetry(), telemetry()]} latest={telemetry()} />)
    // label appears once as a gauge and once as a mini-chart title for these four
    for (const label of ['EGT', 'Vibration', 'RPM N1', 'Fuel Flow'])
      expect(screen.getAllByText(label)).toHaveLength(2)
  })
})
