'use client'

import { AgentActivity } from '@/hooks/useWebSocket'

interface Props {
  events: AgentActivity[]
}

const agentColors: Record<string, string> = {
  telemetry_monitor: 'text-blue-400',
  digital_twin_sync: 'text-purple-400',
  fault_predictor: 'text-orange-400',
  maintenance_planner: 'text-green-400',
  system: 'text-gray-400',
  api: 'text-cyan-400',
  dashboard: 'text-pink-400',
}

const agentIcons: Record<string, string> = {
  telemetry_monitor: '📡',
  digital_twin_sync: '🧬',
  fault_predictor: '⚠️',
  maintenance_planner: '🔧',
  system: '⚙️',
  api: '🌐',
  dashboard: '📊',
}

export default function AgentActivityLog({ events }: Props) {
  const recent = events.slice(-30).reverse()

  return (
    <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">🤖 Agent Activity</h2>

      <div className="space-y-1 max-h-64 overflow-y-auto font-mono text-xs">
        {recent.length === 0 ? (
          <p className="text-gray-500 py-2 font-sans">Waiting for agent events...</p>
        ) : (
          recent.map((evt, i) => (
            <div key={i} className="flex gap-2 py-1 border-b border-aero-border/30">
              <span className="text-gray-600 w-16 shrink-0">
                {new Date(evt.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span className="shrink-0">{agentIcons[evt.agent] ?? '🔵'}</span>
              <span className={`shrink-0 w-28 ${agentColors[evt.agent] ?? 'text-gray-400'}`}>
                {evt.agent.replace(/_/g, ' ')}
              </span>
              <span className="text-gray-300 truncate">{evt.summary}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
