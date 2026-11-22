'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useWebSocket } from '@/hooks/useWebSocket'
import { injectFault, resetSimulator } from '@/lib/api'
import TelemetryCharts from '@/components/TelemetryCharts'
import FaultTimeline from '@/components/FaultTimeline'
import MaintenancePanel from '@/components/MaintenancePanel'
import AgentActivityLog from '@/components/AgentActivityLog'
import EngineSchematic from '@/components/EngineSchematic'
import FaultInjectionButtons from '@/components/FaultInjectionButtons'

export default function DashboardPage() {
  const router = useRouter()
  const [role, setRole] = useState('operator')
  const [username, setUsername] = useState('')
  const { connected, latest, history, agentEvents, sendCommand } = useWebSocket()

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/')
      return
    }
    setRole(localStorage.getItem('role') ?? 'operator')
    // Decode username from JWT
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      setUsername(payload.sub ?? '')
    } catch { /* ignore */ }
  }, [router])

  const handleInjectFault = async (scenario: string) => {
    try {
      await injectFault(scenario)
    } catch {
      // Fallback: send via WebSocket
      sendCommand('inject_fault', scenario)
    }
  }

  const handleReset = async () => {
    try {
      await resetSimulator()
    } catch {
      sendCommand('inject_fault', 'none')
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    router.push('/')
  }

  const statusColor = latest?.engine_status === 'critical' ? 'bg-aero-red' :
    latest?.engine_status === 'warning' ? 'bg-aero-yellow' : 'bg-aero-green'

  const roleLabel = {
    operator: '👁️ Operator',
    maintenance_engineer: '🔧 Engineer',
    admin: '⚙️ Admin',
  }

  return (
    <div className="min-h-screen bg-aero-dark">
      {/* Header */}
      <header className="bg-aero-panel border-b border-aero-border px-4 py-2 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-white">
            ✈️ Aero<span className="text-aero-accent">Twin</span>
          </h1>
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-aero-green status-pulse' : 'bg-gray-600'}`} />
            <span className="text-xs text-gray-400">{connected ? 'Live' : 'Connecting...'}</span>
          </div>
          {latest && (
            <div className={`px-2 py-0.5 rounded text-xs font-bold ${statusColor} text-white`}>
              {latest.engine_status.toUpperCase()}
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-400">
            {roleLabel[role as keyof typeof roleLabel] ?? role} • {username}
          </span>
          <button onClick={handleLogout} className="text-xs text-gray-500 hover:text-white transition">
            Logout
          </button>
        </div>
      </header>

      {/* Dashboard Grid */}
      <main className="p-4 max-w-[1600px] mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left Column — Telemetry Charts (spans 2 cols) */}
          <div className="lg:col-span-2 space-y-4">
            <TelemetryCharts history={history} latest={latest} />
            <EngineSchematic latest={latest} />
          </div>

          {/* Right Column — Status & Predictions */}
          <div className="space-y-4">
            <FaultTimeline latest={latest} history={history} />
            <MaintenancePanel latest={latest} />
            <FaultInjectionButtons
              onInjectFault={handleInjectFault}
              onReset={handleReset}
              role={role}
            />
          </div>

          {/* Bottom Full Width — Agent Activity */}
          <div className="lg:col-span-3">
            <AgentActivityLog events={agentEvents} />
          </div>
        </div>
      </main>
    </div>
  )
}
