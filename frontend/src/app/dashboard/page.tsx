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
import AlertToast from '@/components/AlertToast'

export default function DashboardPage() {
  const router = useRouter()
  const [role, setRole] = useState('operator')
  const [username, setUsername] = useState('')
  const { connected, latest, history, agentEvents, maintenance, sendCommand } = useWebSocket()

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

  const roleLabel: Record<string, string> = {
    operator: '👁️ Operator',
    maintenance_engineer: '🔧 Engineer',
    admin: '⚙️ Admin',
  }

  const roleBadgeColor: Record<string, string> = {
    operator: 'bg-green-900/40 text-green-300 border-green-800/50',
    maintenance_engineer: 'bg-yellow-900/40 text-yellow-300 border-yellow-800/50',
    admin: 'bg-red-900/40 text-red-300 border-red-800/50',
  }

  const canSeeMaintenanceDetails = role !== 'operator'
  const canSeeAgentLog = role === 'admin' || role === 'maintenance_engineer'

  return (
    <div className="min-h-screen bg-aero-dark">
      {/* Alert Toasts */}
      <AlertToast latest={latest} />

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

        <div className="flex items-center gap-3">
          <span className={`text-[10px] px-2 py-0.5 rounded border ${roleBadgeColor[role] ?? 'bg-gray-800 text-gray-300 border-gray-700'}`}>
            {roleLabel[role] ?? role}
          </span>
          <span className="text-xs text-gray-400">{username}</span>
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

            {/* Maintenance: full details for engineers/admins, summary for operators */}
            {canSeeMaintenanceDetails ? (
              <MaintenancePanel latest={latest} maintenance={maintenance} />
            ) : (
              <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
                <h2 className="text-sm font-semibold text-gray-300 mb-3">🔧 Maintenance Status</h2>
                {latest?.fault_type && latest.fault_type !== 'none' ? (
                  <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-lg p-3 text-center">
                    <p className="text-aero-yellow font-medium text-sm">
                      ⚡ Maintenance action required
                    </p>
                    <p className="text-xs text-gray-400 mt-1">Contact maintenance engineer for details</p>
                  </div>
                ) : (
                  <div className="bg-green-900/20 border border-green-800/50 rounded-lg p-3 text-center">
                    <p className="text-aero-green font-medium text-sm">✅ No maintenance required</p>
                  </div>
                )}
              </div>
            )}

            <FaultInjectionButtons
              onInjectFault={handleInjectFault}
              onReset={handleReset}
              role={role}
            />
          </div>

          {/* Bottom Full Width — Agent Activity (engineers + admins only) */}
          {canSeeAgentLog && (
            <div className="lg:col-span-3">
              <AgentActivityLog events={agentEvents} />
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center py-3 text-xs text-gray-600 border-t border-aero-border/30">
        AeroTwin v1.0 • SIH 2026 — SIH26054 • UAV Engine Digital-Twin Health Monitoring
      </footer>
    </div>
  )
}
