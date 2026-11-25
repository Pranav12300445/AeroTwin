"""
Anomaly Detection via z-score against a calibrated baseline + RUL prediction.

Detects deviations from normal engine operating patterns.
High z-score across any sensor channel = anomaly.
"""

from typing import Optional


class AnomalyDetector:
    """
    Lightweight anomaly detector: z-score of each channel against a fixed, calibrated baseline.

    Why fixed and not a rolling window: a baseline that keeps learning from incoming data also
    learns the fault. Measured on the simulator, a rolling-window detector "forgot" bearing wear
    after ~30 s (vibration still ~8 g) and absorbed fuel-nozzle clogging entirely, because slow
    drift moves both the window mean and std. A fixed baseline cannot be talked into accepting it.

    ponytail: upgrade path is a trained model (LSTM autoencoder) on real run-to-failure data.
    """

    # Feature order: egt, rpm_n1, rpm_n2, vibration, fuel_flow, oil_pressure, oil_temp
    FEATURE_NAMES = ["egt", "rpm_n1", "rpm_n2", "vibration", "fuel_flow", "oil_pressure", "oil_temp"]

    # Normal operating (mean, std). EGT / RPM / fuel flow std cover the +-15 % throttle swing of
    # normal cruise (std ~ 8 % of nominal), otherwise ordinary throttle changes raise false alarms.
    NORMAL_STATS = {
        "egt":          (630.0, 50.0),
        "rpm_n1":       (73000.0, 5500.0),
        "rpm_n2":       (77000.0, 5500.0),
        "vibration":    (0.7, 0.3),
        "fuel_flow":    (0.45, 0.04),
        "oil_pressure": (55.0, 5.0),
        "oil_temp":     (82.0, 6.0),
    }

    # Anomaly threshold — z-score above this is anomalous
    ANOMALY_THRESHOLD = 3.0

    def _extract_features(self, reading_dict: dict) -> dict[str, float]:
        return {f: reading_dict.get(f, 0.0) for f in self.FEATURE_NAMES}

    def score(self, reading_dict: dict) -> dict:
        """
        Score a telemetry reading for anomalies.

        Returns:
            anomaly_score: float (0-1, higher = more anomalous)
            is_anomaly: bool
            feature_scores: dict of per-feature z-scores
            top_anomaly_feature: name of the channel with the highest z-score
        """
        features = self._extract_features(reading_dict)

        z_scores = {
            f: abs(features[f] - mean) / std
            for f, (mean, std) in self.NORMAL_STATS.items()
        }

        # Composite anomaly score = max z-score normalized to [0, 1]
        max_z = max(z_scores.values())
        anomaly_score = min(1.0, max_z / (self.ANOMALY_THRESHOLD * 2))

        return {
            "anomaly_score": round(anomaly_score, 4),
            "is_anomaly": bool(max_z > self.ANOMALY_THRESHOLD),
            "feature_scores": {f: round(float(z), 3) for f, z in z_scores.items()},
            "top_anomaly_feature": max(z_scores, key=z_scores.get),
        }


def classify_fault(feature_scores: dict[str, float], threshold: float = AnomalyDetector.ANOMALY_THRESHOLD) -> str:
    """
    Map a per-feature z-score signature to a fault type ("none" if nothing is anomalous).

    Classifying on the single top feature does not work: compressor stall and bearing wear are
    both vibration-dominated, so stall was labelled bearing_wear ~90 % of the time. Signatures:
        compressor_stall  vibration up TOGETHER WITH spool speed / fuel flow / EGT upset
        fuel_nozzle_clog  fuel flow off, vibration normal
        bearing_wear      vibration / oil pressure / oil temp, spool speed and fuel normal
    ponytail: hand-written rules; upgrade path is a classifier trained on labelled run-to-failure data.
    """
    z = feature_scores
    corroborated = 2.5  # secondary channels only need to be clearly off, not past the alarm line
    rpm = max(z.get("rpm_n1", 0.0), z.get("rpm_n2", 0.0))
    vibrating = z.get("vibration", 0.0) > threshold

    if vibrating and (rpm > corroborated or z.get("fuel_flow", 0.0) > corroborated
                      or z.get("egt", 0.0) > corroborated):
        return "compressor_stall"
    if z.get("fuel_flow", 0.0) > threshold and not vibrating:
        return "fuel_nozzle_clog"
    if max(z.get("vibration", 0.0), z.get("oil_pressure", 0.0), z.get("oil_temp", 0.0)) > threshold:
        return "bearing_wear"
    if rpm > threshold:
        return "compressor_stall"
    if z.get("egt", 0.0) > threshold:
        return "turbine_erosion"
    return "none"


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

