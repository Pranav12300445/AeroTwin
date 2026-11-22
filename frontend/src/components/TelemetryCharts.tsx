'use client'

import { TelemetryData } from '@/hooks/useWebSocket'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine } from 'recharts'

interface Props {
  history: TelemetryData[]
  latest: TelemetryData | null
}

function Gauge({ label, value, unit, min, max, warnLow, warnHigh, critLow, critHigh }: {
  label: string; value: number; unit: string
  min: number; max: number
  warnLow?: number; warnHigh?: number
  critLow?: number; critHigh?: number
}) {
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
  let color = 'bg-aero-green'
  let glow = 'glow-green'

  if ((critHigh && value > critHigh) || (critLow && value < critLow)) {
    color = 'bg-aero-red'; glow = 'glow-red'
  } else if ((warnHigh && value > warnHigh) || (warnLow && value < warnLow)) {
    color = 'bg-aero-yellow'; glow = 'glow-yellow'
  }

  return (
    <div className={`bg-aero-dark rounded-lg p-3 border border-aero-border ${glow}`}>
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-xs text-gray-400">{label}</span>
        <span className="text-sm font-mono font-bold text-white">{value.toFixed(1)} <span className="text-gray-500 text-xs">{unit}</span></span>
      </div>
      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function MiniChart({ data, dataKey, color, label }: { data: TelemetryData[]; dataKey: string; color: string; label: string }) {
  const chartData = data.slice(-60).map((d, i) => ({ i, v: (d as any)[dataKey] }))

  return (
    <div className="bg-aero-dark rounded-lg p-3 border border-aero-border">
      <span className="text-xs text-gray-400">{label}</span>
      <div className="h-20 mt-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false} />
            <YAxis hide domain={['auto', 'auto']} />
            <XAxis hide dataKey="i" />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ display: 'none' }}
              formatter={(v: number) => [v.toFixed(2), label]}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function TelemetryCharts({ history, latest }: Props) {
  if (!latest) {
    return (
      <div className="bg-aero-panel rounded-xl border border-aero-border p-6">
        <h2 className="text-lg font-semibold mb-4">📈 Real-time Telemetry</h2>
        <p className="text-gray-500 text-sm">Waiting for telemetry data...</p>
      </div>
    )
  }

  return (
    <div className="bg-aero-panel rounded-xl border border-aero-border p-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">📈 Real-time Telemetry</h2>

      {/* Gauges */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-3">
        <Gauge label="EGT" value={latest.egt} unit="°C" min={0} max={1000} warnHigh={700} critHigh={800} />
        <Gauge label="RPM N1" value={latest.rpm_n1} unit="" min={0} max={100000} warnLow={65000} warnHigh={80000} critHigh={85000} />
        <Gauge label="Vibration" value={latest.vibration} unit="g" min={0} max={10} warnHigh={2.0} critHigh={4.0} />
        <Gauge label="Oil Pressure" value={latest.oil_pressure} unit="PSI" min={0} max={100} warnLow={40} critLow={30} />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 mb-3">
        <Gauge label="Fuel Flow" value={latest.fuel_flow} unit="L/min" min={0} max={1} warnLow={0.25} critLow={0.15} />
        <Gauge label="Oil Temp" value={latest.oil_temp} unit="°C" min={0} max={150} warnHigh={105} critHigh={120} />
        <Gauge label="RPM N2" value={latest.rpm_n2} unit="" min={0} max={100000} warnLow={69000} warnHigh={84000} />
      </div>

      {/* Mini Charts */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <MiniChart data={history} dataKey="egt" color="#ef4444" label="EGT" />
        <MiniChart data={history} dataKey="vibration" color="#f97316" label="Vibration" />
        <MiniChart data={history} dataKey="rpm_n1" color="#3b82f6" label="RPM N1" />
        <MiniChart data={history} dataKey="fuel_flow" color="#22c55e" label="Fuel Flow" />
      </div>
    </div>
  )
}
