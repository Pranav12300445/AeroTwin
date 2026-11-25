import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MaintenancePanel from './MaintenancePanel'
import { telemetry, faulty } from '@/test-utils'
import type { MaintenanceRecommendation } from '@/hooks/useWebSocket'

const rec = (over: Partial<MaintenanceRecommendation> = {}): MaintenanceRecommendation => ({
  fault_type: 'bearing_wear', confidence: 0.9, rul_hours: 12, priority: 'urgent',
  procedure_summary: 'Replace the bearings. Then test.', steps: ['Rotate shaft', 'Measure play'],
  estimated_downtime: '6 hours', safety_note: 'Let the engine cool.', source_documents: ['bearing_inspection.md'],
  llm_enhanced: true, message: 'm', ...over,
})

describe('MaintenancePanel', () => {
  it('says no maintenance is needed for a healthy engine (or no data)', () => {
    const { rerender } = render(<MaintenancePanel latest={null} maintenance={null} />)
    expect(screen.getByText(/No maintenance required/)).toBeInTheDocument()
    rerender(<MaintenancePanel latest={telemetry()} maintenance={null} />)
    expect(screen.getByText(/No maintenance required/)).toBeInTheDocument()
  })

  it.each([
    ['bearing_wear', 'Bearing Inspection & Replacement'],
    ['compressor_stall', 'Compressor Stall Recovery & Inspection'],
    ['fuel_nozzle_clog', 'Fuel Nozzle Cleaning & Inspection'],
    ['turbine_erosion', 'Turbine Blade Inspection'],
  ])('falls back to the built-in procedure for %s when no AI recommendation exists', (fault, title) => {
    render(<MaintenancePanel latest={faulty(fault)} maintenance={null} />)
    expect(screen.getByText(title)).toBeInTheDocument()
    expect(screen.queryByText(/AI-Enhanced/)).not.toBeInTheDocument()
    expect(screen.getByText('🚨 EMERGENCY')).toBeInTheDocument()   // critical status
  })

  it('unknown faults still get a generic inspection', () => {
    render(<MaintenancePanel latest={faulty('mystery_fault')} maintenance={null} />)
    expect(screen.getByText(/mystery fault Inspection/)).toBeInTheDocument()
    expect(screen.getByText('Schedule detailed inspection')).toBeInTheDocument()
  })

  it('fallback priority is URGENT for non-critical status', () => {
    render(<MaintenancePanel latest={faulty('bearing_wear', { engine_status: 'warning' })} maintenance={null} />)
    expect(screen.getByText('⚡ URGENT')).toBeInTheDocument()
  })

  it('shows the AI recommendation: badge, summary, steps, downtime, safety note, source', () => {
    render(<MaintenancePanel latest={faulty('bearing_wear')} maintenance={rec()} />)
    expect(screen.getByText(/AI-Enhanced/)).toBeInTheDocument()
    expect(screen.getByText('Replace the bearings')).toBeInTheDocument()     // title = first sentence
    expect(screen.getByText('Replace the bearings. Then test.')).toBeInTheDocument()
    expect(screen.getByText('Rotate shaft')).toBeInTheDocument()
    expect(screen.getByText('6 hours')).toBeInTheDocument()
    expect(screen.getByText(/Let the engine cool/)).toBeInTheDocument()
    expect(screen.getByText(/Source: bearing_inspection.md/)).toBeInTheDocument()
    expect(screen.getByText('⚡ URGENT')).toBeInTheDocument()
  })

  it('maps routine priority', () => {
    render(<MaintenancePanel latest={faulty('bearing_wear')} maintenance={rec({ priority: 'routine' })} />)
    expect(screen.getByText('📋 ROUTINE')).toBeInTheDocument()
  })

  it('AI recommendation without steps falls back to the built-in steps', () => {
    render(<MaintenancePanel latest={faulty('bearing_wear')} maintenance={rec({ steps: [] })} />)
    expect(screen.getByText(/Rotate shaft by hand/)).toBeInTheDocument()
  })

  it('non-LLM recommendation (RAG text only) uses the fallback view', () => {
    render(<MaintenancePanel latest={faulty('bearing_wear')} maintenance={rec({ llm_enhanced: false })} />)
    expect(screen.queryByText(/AI-Enhanced/)).not.toBeInTheDocument()
    expect(screen.getByText('Bearing Inspection & Replacement')).toBeInTheDocument()
  })

  it('omits the safety note when empty', () => {
    render(<MaintenancePanel latest={faulty('bearing_wear')} maintenance={rec({ safety_note: '' })} />)
    expect(screen.queryByText(/⚠️/)).not.toBeInTheDocument()
  })
})
