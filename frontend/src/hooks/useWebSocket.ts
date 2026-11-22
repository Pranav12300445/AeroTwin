'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { createTelemetrySocket } from '@/lib/api'

export interface TelemetryData {
  timestamp: string
  engine_id: string
  egt: number
  rpm_n1: number
  rpm_n2: number
  vibration: number
  fuel_flow: number
  oil_pressure: number
  oil_temp: number
  oat: number
  altitude: number
  twin_expected_egt: number
  twin_residual: number
  twin_health_factor: number
  twin_drift_detected: boolean
  anomaly_score: number
  is_anomaly: boolean
  top_anomaly_feature: string
  fault_type: string
  rul_hours: number | null
  engine_status: 'normal' | 'warning' | 'critical'
}

export interface AgentActivity {
  timestamp: string
  agent: string
  event: string
  summary: string
}

const MAX_HISTORY = 120

export function useWebSocket() {
  const [connected, setConnected] = useState(false)
  const [latest, setLatest] = useState<TelemetryData | null>(null)
  const [history, setHistory] = useState<TelemetryData[]>([])
  const [agentEvents, setAgentEvents] = useState<AgentActivity[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    try {
      const ws = createTelemetrySocket()
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'telemetry') {
            const data = msg.data as TelemetryData
            setLatest(data)
            setHistory((prev) => {
              const next = [...prev, data]
              return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
            })

            // Collect agent events from anomaly/fault data
            if (data.is_anomaly) {
              setAgentEvents((prev) => {
                const evt: AgentActivity = {
                  timestamp: data.timestamp,
                  agent: 'telemetry_monitor',
                  event: 'anomaly.detected',
                  summary: `Anomaly: ${data.top_anomaly_feature} (score: ${data.anomaly_score.toFixed(3)})`,
                }
                return [...prev.slice(-99), evt]
              })
            }
            if (data.fault_type && data.fault_type !== 'none') {
              setAgentEvents((prev) => {
                const evt: AgentActivity = {
                  timestamp: data.timestamp,
                  agent: 'fault_predictor',
                  event: 'fault.predicted',
                  summary: `${data.fault_type.replace(/_/g, ' ')} — RUL: ${data.rul_hours ?? '?'}h`,
                }
                return [...prev.slice(-99), evt]
              })
            }
          }
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        setConnected(false)
        reconnectRef.current = setTimeout(connect, 3000)
      }

      ws.onerror = () => ws.close()
    } catch {
      reconnectRef.current = setTimeout(connect, 3000)
    }
  }, [])

  const sendCommand = useCallback((action: string, scenario?: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, scenario }))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, latest, history, agentEvents, sendCommand }
}
