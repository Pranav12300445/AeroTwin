import type { TelemetryData } from '@/hooks/useWebSocket'

export function telemetry(over: Partial<TelemetryData> = {}): TelemetryData {
  return {
    timestamp: '2026-11-23T09:00:00+00:00', engine_id: 'engine-001',
    egt: 630, rpm_n1: 73000, rpm_n2: 77000, vibration: 0.7, fuel_flow: 0.45,
    oil_pressure: 55, oil_temp: 82, oat: 25, altitude: 500,
    twin_expected_egt: 630, twin_residual: 0, twin_health_factor: 1, twin_drift_detected: false,
    anomaly_score: 0, is_anomaly: false, top_anomaly_feature: 'egt', fault_type: 'none',
    rul_hours: null, engine_status: 'normal', ...over,
  }
}

export const faulty = (fault: string, over: Partial<TelemetryData> = {}) =>
  telemetry({ is_anomaly: true, fault_type: fault, anomaly_score: 0.9, engine_status: 'critical',
              rul_hours: 12.5, top_anomaly_feature: 'vibration', ...over })
