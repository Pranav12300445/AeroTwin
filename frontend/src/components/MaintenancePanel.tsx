'use client'

import { TelemetryData, MaintenanceRecommendation } from '@/hooks/useWebSocket'

interface Props {
  latest: TelemetryData | null
  maintenance: MaintenanceRecommendation | null
}

// Fallback procedures when LLM is unavailable
const FALLBACK_PROCEDURES: Record<string, { title: string; doc: string; steps: string[]; parts: string[]; downtime: string }> = {
  bearing_wear: {
    title: 'Bearing Inspection & Replacement',
    doc: 'MX-PROC-001',
    steps: [
      'Rotate shaft by hand — check for roughness',
      'Measure radial play (MAX: 0.05mm)',
      'Inspect races for pitting or discoloration',
      'If worn: extract bearing, clean seat, press-fit new bearing',
      'Post-replacement: idle test 5 min, monitor vibration < 1.5g',
    ],
    parts: ['Ceramic hybrid bearings', 'High-temp grease (Kluber)', 'Retaining hardware'],
    downtime: '6–8 hours (replacement)',
  },
  compressor_stall: {
    title: 'Compressor Stall Recovery & Inspection',
    doc: 'MX-PROC-002',
    steps: [
      'THROTTLE — IDLE immediately',
      'WAIT 10 seconds, then slowly advance to 50%',
      'If stall recurs — ENGINE SHUTDOWN',
      'Ground: borescope inspect each compressor stage',
      'Review flight data with digital twin comparison',
    ],
    parts: ['Borescope kit', 'Replacement blades (if damaged)'],
    downtime: '4–6 hours (inspection), 3–5 days (overhaul)',
  },
  fuel_nozzle_clog: {
    title: 'Fuel Nozzle Cleaning & Inspection',
    doc: 'MX-PROC-003',
    steps: [
      'Drain fuel system into approved container',
      'Remove nozzles — note position numbering',
      'Ultrasonic bath at 40°C for 15 minutes',
      'Flow bench test — must be within ±5% rated flow',
      'Replace all O-rings, reinstall, leak check',
    ],
    parts: ['Nozzle O-rings', 'Fuel filter elements', 'Approved solvent'],
    downtime: '3–4 hours (cleaning)',
  },
  turbine_erosion: {
    title: 'Turbine Blade Inspection',
    doc: 'MX-PROC-004',
    steps: [
      'Borescope inspection of turbine section',
      'Check blade tip clearances',
      'Inspect for erosion, cracking, or coating loss',
      'Compare with baseline measurements',
    ],
    parts: ['Borescope kit'],
    downtime: '4–6 hours',
  },
}

export default function MaintenancePanel({ latest, maintenance }: Props) {
  if (!latest || !latest.fault_type || latest.fault_type === 'none') {
    return (
      <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">🔧 Maintenance Recommendations</h2>
        <div className="bg-green-900/20 border border-green-800/50 rounded-lg p-4 text-center">
          <p className="text-aero-green font-medium">✅ No maintenance required</p>
          <p className="text-xs text-gray-500 mt-1">Engine operating within normal parameters</p>
        </div>
      </div>
    )
  }

  const fault = latest.fault_type

  // Use LLM-enhanced recommendation if available, otherwise fallback
  const hasLLM = maintenance && maintenance.llm_enhanced
  const fallback = FALLBACK_PROCEDURES[fault]
  const title = hasLLM ? maintenance.procedure_summary?.split('.')[0] : (fallback?.title ?? `${fault.replace(/_/g, ' ')} Inspection`)
  const steps = hasLLM && maintenance.steps.length > 0 ? maintenance.steps : (fallback?.steps ?? ['Schedule detailed inspection'])
  const downtime = hasLLM ? maintenance.estimated_downtime : (fallback?.downtime ?? 'TBD')
  const safetyNote = hasLLM ? maintenance.safety_note : ''
  const sourceDoc = hasLLM ? maintenance.source_documents?.join(', ') : (fallback?.doc ?? 'General')
  const parts = fallback?.parts ?? []
  const priority = hasLLM ? maintenance.priority : (latest.engine_status === 'critical' ? 'emergency' : 'urgent')

  const priorityColor = priority === 'emergency'
    ? 'bg-red-900/30 border-red-700 text-aero-red'
    : priority === 'urgent'
      ? 'bg-yellow-900/30 border-yellow-700 text-aero-yellow'
      : 'bg-blue-900/30 border-blue-700 text-aero-accent'

  const priorityLabel = priority === 'emergency' ? '🚨 EMERGENCY' : priority === 'urgent' ? '⚡ URGENT' : '📋 ROUTINE'

  return (
    <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-300">🔧 Maintenance Recommendations</h2>
        {hasLLM && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300 border border-purple-800/50">
            🤖 AI-Enhanced
          </span>
        )}
      </div>

      <div className={`rounded-lg border p-3 mb-3 ${priorityColor}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="font-bold text-sm">{priorityLabel}</span>
          <span className="text-xs text-gray-400">Source: {sourceDoc}</span>
        </div>
        <p className="text-white font-medium text-sm">{title}</p>
        {hasLLM && maintenance.procedure_summary && (
          <p className="text-xs text-gray-300 mt-1">{maintenance.procedure_summary}</p>
        )}
      </div>

      {/* Safety Note */}
      {safetyNote && (
        <div className="bg-red-950/30 border border-red-900/50 rounded-lg p-2 mb-3 text-xs text-red-300">
          ⚠️ {safetyNote}
        </div>
      )}

      {/* Steps */}
      <div className="mb-3">
        <p className="text-xs text-gray-400 mb-1">Procedure Steps:</p>
        <ol className="space-y-1 text-xs text-gray-300">
          {steps.map((step, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-gray-500 shrink-0">{i + 1}.</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Parts & Downtime */}
      <div className="flex gap-4 text-xs">
        {parts.length > 0 && (
          <div>
            <span className="text-gray-500">Parts: </span>
            <span className="text-gray-300">{parts.join(', ')}</span>
          </div>
        )}
        <div>
          <span className="text-gray-500">Downtime: </span>
          <span className="text-aero-orange">{downtime}</span>
        </div>
      </div>
    </div>
  )
}
