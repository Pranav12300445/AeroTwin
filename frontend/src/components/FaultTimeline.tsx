'use client'

import { TelemetryData } from '@/hooks/useWebSocket'

interface Props {
  latest: TelemetryData | null
  history: TelemetryData[]
}

export default function FaultTimeline({ latest, history }: Props) {
  const faultEvents = history.filter(d => d.fault_type && d.fault_type !== 'none')
  const recentFaults = faultEvents.slice(-10)

  const statusColor = {
    normal: 'text-aero-green',
    warning: 'text-aero-yellow',
    critical: 'text-aero-red',
  }

  const statusBg = {
    normal: 'bg-green-900/30 border-green-800',
    warning: 'bg-yellow-900/30 border-yellow-800',
    critical: 'bg-red-900/30 border-red-800',
  }

  return (
    <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">⚠️ Fault Prediction & RUL</h2>

      {/* Current Status */}
      {latest && (
        <div className={`rounded-lg border p-3 mb-3 ${statusBg[latest.engine_status]}`}>
          <div className="flex items-center justify-between">
            <div>
              <span className={`text-lg font-bold ${statusColor[latest.engine_status]}`}>
                {latest.engine_status.toUpperCase()}
              </span>
              <p className="text-xs text-gray-400 mt-0.5">
                Anomaly Score: {(latest.anomaly_score * 100).toFixed(1)}%
              </p>
            </div>
            <div className="text-right">
              {latest.fault_type && latest.fault_type !== 'none' ? (
                <>
                  <p className="text-sm font-medium text-white">
                    {latest.fault_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </p>
                  {latest.rul_hours !== null && (
                    <p className="text-2xl font-bold text-aero-orange">
                      {latest.rul_hours.toFixed(1)}h
                      <span className="text-xs text-gray-400 ml-1">RUL</span>
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-gray-500">No faults detected</p>
              )}
            </div>
          </div>

          {/* Twin health */}
          <div className="mt-2 flex items-center gap-4 text-xs">
            <span className="text-gray-400">
              Twin Health: <span className="text-white font-mono">{((latest.twin_health_factor ?? 1) * 100).toFixed(1)}%</span>
            </span>
            <span className="text-gray-400">
              Residual: <span className="text-white font-mono">{(latest.twin_residual ?? 0).toFixed(1)}°C</span>
            </span>
            {latest.twin_drift_detected && (
              <span className="text-aero-yellow font-medium">⚡ Drift Detected</span>
            )}
          </div>
        </div>
      )}

      {/* Fault History Timeline */}
      <div className="space-y-1 max-h-40 overflow-y-auto">
        {recentFaults.length === 0 ? (
          <p className="text-xs text-gray-500 py-2">No fault events yet</p>
        ) : (
          recentFaults.reverse().map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-xs py-1 border-b border-aero-border/50">
              <span className={`w-2 h-2 rounded-full ${f.engine_status === 'critical' ? 'bg-aero-red' : 'bg-aero-yellow'}`} />
              <span className="text-gray-500 font-mono w-16">
                {new Date(f.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span className="text-gray-300">{f.fault_type.replace(/_/g, ' ')}</span>
              {f.rul_hours !== null && (
                <span className="text-aero-orange ml-auto">RUL: {f.rul_hours.toFixed(1)}h</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
