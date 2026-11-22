"""
Physics-Informed Digital Twin.

Simplified Brayton-cycle model that predicts expected EGT given:
    fuel_flow, rpm_n1, rpm_n2, oat, altitude

The residual (actual EGT - expected EGT) feeds the Fault Predictor.
Large residuals indicate engine degradation.
"""

from ..models.schemas import TelemetryReading


class DigitalTwin:
    """
    Physics-informed engine model.

    Uses simplified thermodynamic relationships:
        EGT ≈ f(fuel_flow, RPM, ambient conditions)

    The model tracks a "health factor" that degrades over time
    based on observed residuals, simulating long-term wear.
    """

    def __init__(self, engine_id: str = "engine-001"):
        self.engine_id = engine_id

        # Learned coefficients (would be calibrated per engine in production)
        self._base_egt = 300.0           # Base EGT at idle
        self._fuel_coeff = 650.0         # EGT increase per L/min of fuel
        self._rpm_coeff = 0.001          # EGT contribution from RPM
        self._altitude_coeff = -0.005    # EGT drops slightly with altitude (cooler air)
        self._oat_coeff = 0.8            # Ambient temp influence

        # Health tracking
        self._health_factor = 1.0        # 1.0 = new engine, degrades toward 0
        self._residual_history: list[float] = []
        self._max_history = 100

    def predict_egt(self, reading: TelemetryReading) -> float:
        """
        Predict expected EGT from physics model.

        Simplified Brayton-cycle:
            T_exhaust ≈ T_base + k1 * fuel_flow + k2 * avg_rpm + k3 * altitude + k4 * OAT
        """
        avg_rpm = (reading.rpm_n1 + reading.rpm_n2) / 2.0

        expected_egt = (
            self._base_egt
            + self._fuel_coeff * reading.fuel_flow
            + self._rpm_coeff * avg_rpm
            + self._altitude_coeff * reading.altitude
            + self._oat_coeff * reading.oat
        )

        # Apply health factor — degraded engines produce higher EGT
        expected_egt *= self._health_factor

        return round(expected_egt, 2)

    def compute_residual(self, reading: TelemetryReading) -> dict:
        """
        Compute the residual between actual and predicted EGT.

        Returns dict with:
            expected_egt, residual, residual_pct, health_factor, drift_detected
        """
        expected = self.predict_egt(reading)
        residual = reading.egt - expected
        residual_pct = (residual / expected * 100) if expected != 0 else 0

        # Track residual history
        self._residual_history.append(abs(residual))
        if len(self._residual_history) > self._max_history:
            self._residual_history.pop(0)

        # Update health factor based on sustained residuals
        if len(self._residual_history) >= 10:
            avg_residual = sum(self._residual_history[-10:]) / 10
            if avg_residual > 30:
                self._health_factor = max(0.5, self._health_factor - 0.001)

        # Drift detection: is the residual trending upward?
        drift_detected = False
        if len(self._residual_history) >= 20:
            recent = sum(self._residual_history[-10:]) / 10
            older = sum(self._residual_history[-20:-10]) / 10
            drift_detected = recent > older * 1.3  # 30% increase

        return {
            "expected_egt": expected,
            "actual_egt": reading.egt,
            "residual": round(residual, 2),
            "residual_pct": round(residual_pct, 2),
            "health_factor": round(self._health_factor, 4),
            "drift_detected": drift_detected,
        }

    @property
    def health_factor(self) -> float:
        return self._health_factor

    def reset(self):
        """Reset twin state (e.g., after maintenance)."""
        self._health_factor = 1.0
        self._residual_history.clear()

