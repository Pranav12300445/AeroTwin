'use client'

import { useEffect, useRef, useState } from 'react'
import { TelemetryData } from '@/hooks/useWebSocket'

interface Toast {
  id: number
  message: string
  type: 'warning' | 'critical' | 'info'
  timestamp: number
}

interface Props {
  latest: TelemetryData | null
}

let nextId = 0

export default function AlertToast({ latest }: Props) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const prevRef = useRef<{ isAnomaly: boolean; faultType: string }>({ isAnomaly: false, faultType: 'none' })

  useEffect(() => {
    if (!latest) return

    const prev = prevRef.current
    const newToasts: Toast[] = []

    // Anomaly transition: false → true
    if (latest.is_anomaly && !prev.isAnomaly) {
      newToasts.push({
        id: ++nextId,
        message: `⚠️ Anomaly detected! ${latest.top_anomaly_feature} (score: ${(latest.anomaly_score * 100).toFixed(1)}%)`,
        type: latest.engine_status === 'critical' ? 'critical' : 'warning',
        timestamp: Date.now(),
      })
    }

    // Fault type change
    if (latest.fault_type !== 'none' && latest.fault_type !== prev.faultType) {
      newToasts.push({
        id: ++nextId,
        message: `🔴 Fault: ${latest.fault_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} — RUL: ${latest.rul_hours?.toFixed(1) ?? '?'}h`,
        type: 'critical',
        timestamp: Date.now(),
      })
    }

    // Back to normal
    if (!latest.is_anomaly && prev.isAnomaly && prev.faultType !== 'none') {
      newToasts.push({
        id: ++nextId,
        message: '✅ Engine returned to normal parameters',
        type: 'info',
        timestamp: Date.now(),
      })
    }

    prevRef.current = { isAnomaly: latest.is_anomaly, faultType: latest.fault_type }

    if (newToasts.length > 0) {
      setToasts(prev => [...prev, ...newToasts].slice(-5))
    }
  }, [latest])

  // Auto-dismiss after 6 seconds
  useEffect(() => {
    if (toasts.length === 0) return
    const timer = setTimeout(() => {
      setToasts(prev => prev.slice(1))
    }, 6000)
    return () => clearTimeout(timer)
  }, [toasts])

  if (toasts.length === 0) return null

  const colorMap = {
    critical: 'bg-red-900/90 border-red-600 text-red-100',
    warning: 'bg-yellow-900/90 border-yellow-600 text-yellow-100',
    info: 'bg-green-900/90 border-green-600 text-green-100',
  }

  return (
    <div className="fixed top-16 right-4 z-[100] space-y-2 w-80">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`rounded-lg border px-4 py-3 shadow-lg toast-enter ${colorMap[toast.type]}`}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium">{toast.message}</p>
            <button
              onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}
              className="text-xs opacity-60 hover:opacity-100 shrink-0"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
