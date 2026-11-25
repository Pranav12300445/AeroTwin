"""Tests for anomaly detection and RUL prediction."""

from app.ml.anomaly import AnomalyDetector, RULPredictor


def test_anomaly_detector_normal_reading_is_not_anomaly(anomaly_detector):
    reading = {
        "egt": 630.0,
        "rpm_n1": 73000.0,
        "rpm_n2": 77000.0,
        "vibration": 0.7,
        "fuel_flow": 0.45,
        "oil_pressure": 55.0,
        "oil_temp": 82.0,
    }
    result = anomaly_detector.score(reading)
    assert result["is_anomaly"] is False
    assert result["anomaly_score"] < 0.5
    assert "top_anomaly_feature" in result
    assert set(result["feature_scores"].keys()) == set(AnomalyDetector.FEATURE_NAMES)


def test_anomaly_detector_extreme_reading_is_anomaly(anomaly_detector):
    # Feed several normal readings first to calibrate running stats
    for _ in range(15):
        anomaly_detector.score({
            "egt": 630.0,
            "rpm_n1": 73000.0,
            "rpm_n2": 77000.0,
            "vibration": 0.7,
            "fuel_flow": 0.45,
            "oil_pressure": 55.0,
            "oil_temp": 82.0,
        })

    # Now an extreme reading should flag as anomaly
    reading = {
        "egt": 900.0,
        "rpm_n1": 73000.0,
        "rpm_n2": 77000.0,
        "vibration": 0.7,
        "fuel_flow": 0.45,
        "oil_pressure": 55.0,
        "oil_temp": 82.0,
    }
    result = anomaly_detector.score(reading)
    assert bool(result["is_anomaly"]) is True
    assert result["top_anomaly_feature"] == "egt"
    assert result["feature_scores"]["egt"] > 3.0


def test_anomaly_detector_missing_features_default_to_zero(anomaly_detector):
    reading = {}
    result = anomaly_detector.score(reading)
    assert result["is_anomaly"] is True  # all zeros are far from normal
    assert result["anomaly_score"] > 0


def test_anomaly_detector_score_range_0_to_1(anomaly_detector):
    for _ in range(15):
        anomaly_detector.score({
            "egt": 630.0,
            "rpm_n1": 73000.0,
            "rpm_n2": 77000.0,
            "vibration": 0.7,
            "fuel_flow": 0.45,
            "oil_pressure": 55.0,
            "oil_temp": 82.0,
        })

    # Max possible anomaly
    extreme = {f: 9999.0 for f in AnomalyDetector.FEATURE_NAMES}
    result = anomaly_detector.score(extreme)
    assert 0.0 <= result["anomaly_score"] <= 1.0


def test_rul_predictor_none_fault_returns_none(rul_predictor):
    assert rul_predictor.predict(0.5, "none") is None


def test_rul_predictor_low_score_returns_none(rul_predictor):
    for _ in range(5):
        assert rul_predictor.predict(0.1, "bearing_wear") is None


def test_rul_predictor_bearing_wear_returns_hours(rul_predictor):
    for _ in range(5):
        rul = rul_predictor.predict(0.6, "bearing_wear")
    assert rul is not None
    assert isinstance(rul, float)
    assert 0.5 <= rul <= 200


def test_rul_predictor_compressor_stall_lower_max_rul(rul_predictor):
    for _ in range(5):
        bearing = rul_predictor.predict(0.6, "bearing_wear")
        stall = rul_predictor.predict(0.6, "compressor_stall")
    assert stall is not None
    assert stall <= bearing  # compressor stall has lower base hours


def test_rul_predictor_clamped_minimum(rul_predictor):
    # Very high anomaly score should clamp to minimum 0.5
    for _ in range(5):
        rul = rul_predictor.predict(0.99, "bearing_wear")
    assert rul is not None
    assert rul >= 0.5
