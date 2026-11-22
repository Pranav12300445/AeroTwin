'use client'

interface Props {
  onInjectFault: (scenario: string) => void
  onReset: () => void
  role: string
}

export default function FaultInjectionButtons({ onInjectFault, onReset, role }: Props) {
  // Only engineers and admins can inject faults
  if (role === 'operator') return null

  return (
    <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">🎮 Demo Scenarios</h2>
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => onInjectFault('bearing_wear')}
          className="bg-red-900/30 hover:bg-red-900/50 border border-red-800/50 rounded-lg p-3 text-left transition"
        >
          <span className="text-sm font-medium text-aero-red">🔴 Bearing Wear</span>
          <p className="text-xs text-gray-400 mt-0.5">Gradual vibration increase (60s)</p>
        </button>

        <button
          onClick={() => onInjectFault('compressor_stall')}
          className="bg-orange-900/30 hover:bg-orange-900/50 border border-orange-800/50 rounded-lg p-3 text-left transition"
        >
          <span className="text-sm font-medium text-aero-orange">🟠 Compressor Stall</span>
          <p className="text-xs text-gray-400 mt-0.5">Sudden RPM spike + EGT surge (5s)</p>
        </button>

        <button
          onClick={() => onInjectFault('fuel_nozzle_clog')}
          className="bg-yellow-900/30 hover:bg-yellow-900/50 border border-yellow-800/50 rounded-lg p-3 text-left transition"
        >
          <span className="text-sm font-medium text-aero-yellow">🟡 Fuel Nozzle Clog</span>
          <p className="text-xs text-gray-400 mt-0.5">Gradual fuel flow drop (30s)</p>
        </button>

        <button
          onClick={() => onReset()}
          className="bg-green-900/30 hover:bg-green-900/50 border border-green-800/50 rounded-lg p-3 text-left transition"
        >
          <span className="text-sm font-medium text-aero-green">✅ Reset Normal</span>
          <p className="text-xs text-gray-400 mt-0.5">Clear faults, back to baseline</p>
        </button>
      </div>
    </div>
  )
}
