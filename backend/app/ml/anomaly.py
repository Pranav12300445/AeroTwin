"""
Anomaly Detection via running z-score + RUL prediction.

Detects deviations from normal engine operating patterns.
High z-score across any sensor channel = anomaly.
"""

import numpy as np
from typing import Optional


class AnomalyDetector:
    """
    Lightweight anomaly detector using statistical z-score approach.

    For the hackathon, we use a running statistics model that
    learns normal behavior and flags deviations. This can be
    upgraded to a trained LSTM Autoencoder with real data.
    """

    # Feature order: egt, rpm_n1, rpm_n2, vibration, fuel_flow, oil_pressure, oil_temp
    FEATURE_NAMES = ["egt", "rpm_n1", "rpm_n2", "vibration", "fuel_flow", "oil_pressure", "oil_temp"]

    # Normal operating ranges (mean, std) — calibrated for JetCat-style engine
    NORMAL_STATS = {
        "egt":          (630.0, 25.0),
        "rpm_n1":       (73000.0, 2000.0),
        "rpm_n2":       (77000.0, 2000.0),
        "vibration":    (0.7, 0.3),
        "fuel_flow":    (0.45, 0.05),
        "oil_pressure": (55.0, 5.0),
        "oil_temp":     (82.0, 6.0),
    }

    # Anomaly threshold — z-score above this is anomalous
    ANOMALY_THRESHOLD = 3.0

    def __init__(self):
        self._window: list[dict[str, float]] = []
        self._window_size = 50
        self._running_means: Optional[dict[str, float]] = None
        self._running_stds: Optional[dict[str, float]] = None

    def _extract_features(self, reading_dict: dict) -> dict[str, float]:
        return {f: reading_dict.get(f, 0.0) for f in self.FEATURE_NAMES}

    def _update_running_stats(self):
        """Update running mean/std from the window."""
        if len(self._window) < 10:
            # Use pre-calibrated stats until we have enough data
            self._running_means = {f: s[0] for f, s in self.NORMAL_STATS.items()}
            self._running_stds = {f: s[1] for f, s in self.NORMAL_STATS.items()}
            return

        self._running_means = {}
        self._running_stds = {}
        for f in self.FEATURE_NAMES:
            vals = [w[f] for w in self._window]
            self._running_means[f] = np.mean(vals)
            self._running_stds[f] = max(np.std(vals), 1e-6)  # prevent div by zero

    def score(self, reading_dict: dict) -> dict:
        """
        Score a telemetry reading for anomalies.

        Returns:
            anomaly_score: float (0-1, higher = more anomalous)
            is_anomaly: bool
            feature_scores: dict of per-feature z-scores
        """
        features = self._extract_features(reading_dict)

        # Add to window
        self._window.append(features)
        if len(self._window) > self._window_size:
            self._window.pop(0)

        self._update_running_stats()

        # Compute z-scores per feature
        z_scores = {}
        for f in self.FEATURE_NAMES:
            mean = self._running_means[f]
            std = self._running_stds[f]
            z_scores[f] = abs(features[f] - mean) / std

        # Composite anomaly score = max z-score normalized to [0, 1]
        max_z = max(z_scores.values())
        anomaly_score = min(1.0, max_z / (self.ANOMALY_THRESHOLD * 2))

        is_anomaly = max_z > self.ANOMALY_THRESHOLD

        return {
            "anomaly_score": round(anomaly_score, 4),
            "is_anomaly": is_anomaly,
            "feature_scores": {f: round(z, 3) for f, z in z_scores.items()},
            "top_anomaly_feature": max(z_scores, key=z_scores.get),
        }


class RULPredictor:
    """
    Remaining Useful Life predictor.

    Uses a simple degradation model based on anomaly trends.
    In production, this would be an MLP trained on run-to-failure data.
    """

    def __init__(self):
        self._anomaly_history: list[float] = []
        self._max_history = 100

    def predict(self, anomaly_score: float, fault_type: str = "none") -> Optional[float]:
        """
        Predict RUL in flight hours.

        Returns None if no degradation detected.
        """
        self._anomaly_history.append(anomaly_score)
        if len(self._anomaly_history) > self._max_history:
            self._anomaly_history.pop(0)

        if fault_type == "none" or anomaly_score < 0.2:
            return None

        # Estimate degradation rate from anomaly trend
        if len(self._anomaly_history) < 5:
            return None

        recent = self._anomaly_history[-5:]
        avg_score = sum(recent) / len(recent)

        # Simple linear extrapolation: how many hours until score reaches 1.0
        if avg_score <= 0.1:
            return None

        # Higher anomaly score = less RUL
        # Rough heuristic: RUL = (1 - avg_score) * base_hours / degradation_rate
        base_hours = {
            "bearing_wear": 200,
            "compressor_stall": 10,
            "fuel_nozzle_clog": 80,
            "turbine_erosion": 150,
            "oil_system_failure": 50,
        }

        max_rul = base_hours.get(fault_type, 100)
        rul = max_rul * (1 - avg_score)

        return round(max(0.5, rul), 1)

