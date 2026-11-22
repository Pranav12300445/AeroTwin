'use client'

import { TelemetryData } from '@/hooks/useWebSocket'

interface Props {
  latest: TelemetryData | null
}

export default function MaintenancePanel({ latest }: Props) {
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
  const procedures: Record<string, { title: string; doc: string; steps: string[]; parts: string[]; downtime: string }> = {
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

  const proc = procedures[fault] ?? {
    title: `${fault.replace(/_/g, ' ')} Inspection`,
    doc: 'General',
    steps: ['Schedule detailed inspection'],
    parts: [],
    downtime: 'TBD',
  }

  const priorityColor = latest.engine_status === 'critical'
    ? 'bg-red-900/30 border-red-700 text-aero-red'
    : 'bg-yellow-900/30 border-yellow-700 text-aero-yellow'

  const priorityLabel = latest.engine_status === 'critical' ? '🚨 EMERGENCY' : '⚡ URGENT'

  return (
    <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">🔧 Maintenance Recommendations</h2>

      <div className={`rounded-lg border p-3 mb-3 ${priorityColor}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="font-bold text-sm">{priorityLabel}</span>
          <span className="text-xs text-gray-400">Source: {proc.doc}</span>
        </div>
        <p className="text-white font-medium text-sm">{proc.title}</p>
      </div>

      {/* Steps */}
      <div className="mb-3">
        <p className="text-xs text-gray-400 mb-1">Procedure Steps:</p>
        <ol className="space-y-1 text-xs text-gray-300">
          {proc.steps.map((step, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-gray-500 shrink-0">{i + 1}.</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Parts & Downtime */}
      <div className="flex gap-4 text-xs">
        <div>
          <span className="text-gray-500">Parts: </span>
          <span className="text-gray-300">{proc.parts.join(', ') || 'None'}</span>
        </div>
        <div>
          <span className="text-gray-500">Downtime: </span>
          <span className="text-aero-orange">{proc.downtime}</span>
        </div>
      </div>
    </div>
  )
}
