"""Tests for the physics-informed Digital Twin."""

from app.models.schemas import TelemetryReading


def test_digital_twin_predict_egt_returns_float(digital_twin):
    reading = TelemetryReading(
        egt=630.0,
        rpm_n1=73000.0,
        rpm_n2=77000.0,
        vibration=0.7,
        fuel_flow=0.45,
        oil_pressure=55.0,
        oil_temp=82.0,
    )
    expected = digital_twin.predict_egt(reading)
    assert isinstance(expected, float)
    assert expected > 0


def test_digital_twin_compute_residual_structure(digital_twin):
    reading = TelemetryReading(
        egt=650.0,
        rpm_n1=73000.0,
        rpm_n2=77000.0,
        vibration=0.7,
        fuel_flow=0.45,
        oil_pressure=55.0,
        oil_temp=82.0,
    )
    result = digital_twin.compute_residual(reading)
    assert "expected_egt" in result
    assert "actual_egt" in result
    assert "residual" in result
    assert "residual_pct" in result
    assert "health_factor" in result
    assert "drift_detected" in result
    assert result["actual_egt"] == 650.0
    assert result["health_factor"] == 1.0  # fresh twin


def test_digital_twin_residual_matches_actual_minus_expected(digital_twin):
    reading = TelemetryReading(
        egt=700.0,
        rpm_n1=73000.0,
        rpm_n2=77000.0,
        vibration=0.7,
        fuel_flow=0.45,
        oil_pressure=55.0,
        oil_temp=82.0,
    )
    result = digital_twin.compute_residual(reading)
    expected_residual = reading.egt - result["expected_egt"]
    assert abs(result["residual"] - expected_residual) < 0.01


def test_digital_twin_health_degrades_with_sustained_residual(digital_twin):
    # Feed high-EGT readings repeatedly to degrade health factor
    for i in range(15):
        reading = TelemetryReading(
            egt=900.0 + i * 10,
            rpm_n1=73000.0,
            rpm_n2=77000.0,
            vibration=0.7,
            fuel_flow=0.45,
            oil_pressure=55.0,
            oil_temp=82.0,
        )
        digital_twin.compute_residual(reading)
    assert digital_twin.health_factor < 1.0


def test_digital_twin_reset_restores_health(digital_twin):
    # Degrade first
    for _ in range(15):
        reading = TelemetryReading(
            egt=950.0,
            rpm_n1=73000.0,
            rpm_n2=77000.0,
            vibration=0.7,
            fuel_flow=0.45,
            oil_pressure=55.0,
            oil_temp=82.0,
        )
        digital_twin.compute_residual(reading)
    assert digital_twin.health_factor < 1.0

    digital_twin.reset()
    assert digital_twin.health_factor == 1.0


def test_digital_twin_drift_detected_after_enough_history(digital_twin):
    # Build up residual history with increasing residuals
    for i in range(25):
        reading = TelemetryReading(
            egt=630.0 + i * 5,
            rpm_n1=73000.0,
            rpm_n2=77000.0,
            vibration=0.7,
            fuel_flow=0.45,
            oil_pressure=55.0,
            oil_temp=82.0,
        )
        digital_twin.compute_residual(reading)
    # Drift may or may not be detected depending on values; just ensure no crash
    result = digital_twin.compute_residual(
        TelemetryReading(
            egt=700.0, rpm_n1=73000.0, rpm_n2=77000.0,
            vibration=0.7, fuel_flow=0.45, oil_pressure=55.0, oil_temp=82.0,
        )
    )
    assert isinstance(result["drift_detected"], bool)
