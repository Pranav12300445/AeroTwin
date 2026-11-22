'use client'

import { TelemetryData } from '@/hooks/useWebSocket'

interface Props {
  latest: TelemetryData | null
}

export default function EngineSchematic({ latest }: Props) {
  const status = latest?.engine_status ?? 'normal'
  const fault = latest?.fault_type ?? 'none'

  const zoneColors = {
    compressor: fault === 'compressor_stall' ? '#ef4444' : (status === 'warning' ? '#eab308' : '#22c55e'),
    combustor: (fault === 'fuel_nozzle_clog' || fault === 'turbine_erosion') ? '#ef4444' : (status === 'warning' ? '#eab308' : '#22c55e'),
    turbine: fault === 'turbine_erosion' ? '#ef4444' : '#22c55e',
    bearing: fault === 'bearing_wear' ? '#ef4444' : '#22c55e',
    exhaust: status === 'critical' ? '#ef4444' : '#22c55e',
  }

  return (
    <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">🧬 Digital Twin — Engine Schematic</h2>

      <div className="relative">
        <svg viewBox="0 0 500 180" className="w-full" xmlns="http://www.w3.org/2000/svg">
          {/* Background */}
          <rect x="0" y="0" width="500" height="180" fill="#0a0e17" rx="8"/>

          {/* Inlet */}
          <path d="M 30 60 L 80 40 L 80 140 L 30 120 Z" fill="#1e293b" stroke="#475569" strokeWidth="1.5"/>
          <text x="45" y="95" fill="#94a3b8" fontSize="8" textAnchor="middle">INLET</text>

          {/* Compressor */}
          <rect x="85" y="35" width="90" height="110" rx="4" fill="#1e293b" stroke={zoneColors.compressor} strokeWidth="2"/>
          {[50, 65, 80, 95, 110, 125].map((y, i) => (
            <line key={i} x1="90" y1={y} x2="170" y2={y} stroke={zoneColors.compressor} strokeWidth="0.8" opacity="0.5"/>
          ))}
          <text x="130" y="155" fill={zoneColors.compressor} fontSize="8" textAnchor="middle" fontWeight="bold">COMPRESSOR</text>

          {/* Combustion Chamber */}
          <rect x="180" y="35" width="80" height="110" rx="4" fill="#1e293b" stroke={zoneColors.combustor} strokeWidth="2"/>
          {/* Flame icon */}
          <text x="220" y="85" fill={zoneColors.combustor} fontSize="20" textAnchor="middle">🔥</text>
          <text x="220" y="155" fill={zoneColors.combustor} fontSize="7" textAnchor="middle" fontWeight="bold">COMBUSTOR</text>

          {/* Nozzles */}
          {fault === 'fuel_nozzle_clog' && (
            <text x="220" y="105" fill="#ef4444" fontSize="7" textAnchor="middle" fontWeight="bold">⚠ CLOGGED</text>
          )}

          {/* Turbine */}
          <rect x="265" y="35" width="80" height="110" rx="4" fill="#1e293b" stroke={zoneColors.turbine} strokeWidth="2"/>
          {[50, 65, 80, 95, 110, 125].map((y, i) => (
            <line key={i} x1="270" y1={y} x2="340" y2={y} stroke={zoneColors.turbine} strokeWidth="0.8" opacity="0.5"/>
          ))}
          <text x="305" y="155" fill={zoneColors.turbine} fontSize="8" textAnchor="middle" fontWeight="bold">TURBINE</text>

          {/* Exhaust */}
          <path d="M 350 40 L 420 55 L 420 125 L 350 140 Z" fill="#1e293b" stroke={zoneColors.exhaust} strokeWidth="1.5"/>
          <text x="385" y="95" fill="#94a3b8" fontSize="8" textAnchor="middle">EXHAUST</text>

          {/* Shaft / Bearing */}
          <line x1="90" y1="90" x2="345" y2="90" stroke={zoneColors.bearing} strokeWidth="3" strokeDasharray={fault === 'bearing_wear' ? '6,3' : 'none'}/>
          <circle cx="130" cy="90" r="6" fill="#0a0e17" stroke={zoneColors.bearing} strokeWidth="2"/>
          <circle cx="305" cy="90" r="6" fill="#0a0e17" stroke={zoneColors.bearing} strokeWidth="2"/>

          {/* Bearing labels */}
          {fault === 'bearing_wear' && (
            <>
              <text x="130" y="30" fill="#ef4444" fontSize="7" textAnchor="middle" fontWeight="bold">⚠ WEAR</text>
              <text x="305" y="30" fill="#ef4444" fontSize="7" textAnchor="middle" fontWeight="bold">⚠ WEAR</text>
            </>
          )}

          {/* EGT probe */}
          <line x1="425" y1="70" x2="460" y2="70" stroke="#f97316" strokeWidth="1.5"/>
          <text x="470" y="73" fill="#f97316" fontSize="7">EGT</text>
          <text x="470" y="83" fill="#f97316" fontSize="9" fontWeight="bold">{latest?.egt.toFixed(0) ?? '—'}°C</text>

          {/* RPM indicator */}
          <text x="470" y="105" fill="#3b82f6" fontSize="7">RPM</text>
          <text x="470" y="115" fill="#3b82f6" fontSize="9" fontWeight="bold">{latest ? (latest.rpm_n1/1000).toFixed(1) : '—'}k</text>

          {/* Status indicator */}
          <circle cx="20" cy="15" r="6" fill={status === 'critical' ? '#ef4444' : status === 'warning' ? '#eab308' : '#22c55e'} className={status === 'normal' ? 'status-pulse' : ''}/>
          <text x="32" y="18" fill="#e2e8f0" fontSize="9" fontWeight="bold">
            {status.toUpperCase()}
          </text>
        </svg>
      </div>
    </div>
  )
}
