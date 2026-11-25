"""Fixed-baseline anomaly detector + signature-based fault classifier, incl. simulator-driven checks."""

import random
from collections import Counter

import pytest

from app.ml.anomaly import AnomalyDetector, RULPredictor, classify_fault
from app.simulator import engine
from app.simulator.engine import EngineSimulator, FaultScenario

NOMINAL = {"egt": 630.0, "rpm_n1": 73000.0, "rpm_n2": 77000.0, "vibration": 0.7,
           "fuel_flow": 0.45, "oil_pressure": 55.0, "oil_temp": 82.0}


def z(**overrides):
    base = {f: 0.0 for f in AnomalyDetector.FEATURE_NAMES}
    base.update(overrides)
    return base


# ── detector ──

def test_nominal_reading_scores_zero(anomaly_detector):
    r = anomaly_detector.score(NOMINAL)
    assert r["is_anomaly"] is False and r["anomaly_score"] == 0.0
    assert all(v == 0 for v in r["feature_scores"].values())


def test_baseline_is_fixed_and_cannot_be_trained_by_a_fault(anomaly_detector):
    """Regression: a rolling baseline 'learned' faults and stopped flagging them after ~30 s."""
    sick = {**NOMINAL, "vibration": 8.0}
    results = [anomaly_detector.score(sick) for _ in range(200)]
    assert all(r["is_anomaly"] for r in results)
    assert results[0]["feature_scores"] == results[-1]["feature_scores"]


def test_each_channel_can_trigger_an_anomaly(anomaly_detector):
    for feature, (mean, std) in AnomalyDetector.NORMAL_STATS.items():
        r = anomaly_detector.score({**NOMINAL, feature: mean + 4 * std})
        assert r["is_anomaly"] is True, feature
        assert r["top_anomaly_feature"] == feature


def test_deviation_below_baseline_also_counts(anomaly_detector):
    assert anomaly_detector.score({**NOMINAL, "fuel_flow": 0.2})["is_anomaly"] is True


def test_threshold_is_strictly_greater_than_three_sigma(anomaly_detector):
    mean, std = AnomalyDetector.NORMAL_STATS["oil_temp"]
    assert anomaly_detector.score({**NOMINAL, "oil_temp": mean + 2.9 * std})["is_anomaly"] is False
    assert anomaly_detector.score({**NOMINAL, "oil_temp": mean + 3.1 * std})["is_anomaly"] is True


def test_anomaly_score_is_max_z_over_six_capped_at_one(anomaly_detector):
    mean, std = AnomalyDetector.NORMAL_STATS["egt"]
    assert anomaly_detector.score({**NOMINAL, "egt": mean + 3 * std})["anomaly_score"] == pytest.approx(0.5, abs=1e-3)
    assert anomaly_detector.score({**NOMINAL, "egt": mean + 60 * std})["anomaly_score"] == 1.0


def test_throttle_swing_of_15_percent_is_not_an_anomaly(anomaly_detector):
    """Normal cruise varies throttle +-15 %; that must not raise alarms."""
    for k in (0.85, 0.9, 1.0, 1.1, 1.15):
        reading = {**NOMINAL, "egt": 630 * k, "rpm_n1": 73000 * k, "rpm_n2": 77000 * k, "fuel_flow": 0.45 * k}
        assert anomaly_detector.score(reading)["is_anomaly"] is False, k


# ── classifier signatures ──

@pytest.mark.parametrize("scores,expected", [
    (z(), "none"),
    (z(vibration=2.9, egt=2.9, fuel_flow=2.9), "none"),                       # nothing past threshold
    (z(vibration=9, oil_temp=5, oil_pressure=4), "bearing_wear"),
    (z(vibration=6), "bearing_wear"),                                          # vibration alone
    (z(oil_temp=3.5), "bearing_wear"),
    (z(oil_pressure=3.5), "bearing_wear"),
    (z(vibration=15, rpm_n1=3.8, rpm_n2=3.1, egt=2.3, fuel_flow=7), "compressor_stall"),
    (z(vibration=12, fuel_flow=3.0), "compressor_stall"),                      # vibration + fuel upset
    (z(vibration=12, egt=2.6), "compressor_stall"),                            # vibration + EGT upset
    (z(vibration=12, rpm_n2=2.6), "compressor_stall"),                         # vibration + spool speed
    (z(rpm_n1=4.0), "compressor_stall"),                                       # speed upset without vibration
    (z(fuel_flow=6, egt=1), "fuel_nozzle_clog"),
    (z(egt=4.5), "turbine_erosion"),
])
def test_classify_fault_signatures(scores, expected):
    assert classify_fault(scores) == expected


def test_stall_is_not_mislabelled_as_bearing_wear_when_vibration_dominates():
    """Regression: top-feature mapping labelled stall (vibration z=15) as bearing_wear ~92 % of the time."""
    assert classify_fault(z(vibration=15, rpm_n1=3.9, fuel_flow=7)) == "compressor_stall"


def test_classify_fault_tolerates_missing_features():
    assert classify_fault({}) == "none"
    assert classify_fault({"vibration": 9}) == "bearing_wear"


# ── end-to-end with the simulator (fake clock => deterministic, instant) ──

def run_scenario(fault, seed, warmup=30, seconds=70):
    random.seed(seed)
    now = [1_000_000.0]
    real_time = engine.time
    engine.time = type("T", (), {"time": staticmethod(lambda: now[0])})
    try:
        sim, det = EngineSimulator(), AnomalyDetector()
        labels = []
        for t in range(warmup + seconds):
            now[0] += 1
            if fault and t == warmup:
                sim.inject_fault(fault)
            r = det.score(sim.generate_reading().model_dump())
            labels.append(classify_fault(r["feature_scores"]) if r["is_anomaly"] else "none")
        return labels[warmup:] if fault else labels
    finally:
        engine.time = real_time


@pytest.mark.parametrize("seed", range(10))
def test_normal_operation_raises_no_alarms(seed):
    assert set(run_scenario(None, seed, seconds=120)) == {"none"}


@pytest.mark.parametrize("fault,label", [
    (FaultScenario.BEARING_WEAR, "bearing_wear"),
    (FaultScenario.COMPRESSOR_STALL, "compressor_stall"),
    (FaultScenario.FUEL_NOZZLE_CLOG, "fuel_nozzle_clog"),
])
@pytest.mark.parametrize("seed", range(10))
def test_injected_fault_is_sustained_and_correctly_labelled(fault, label, seed):
    labels = run_scenario(fault, seed)
    last20 = labels[-20:]
    assert "none" not in last20, "fault must stay flagged until it is cleared"
    assert Counter(last20).most_common(1)[0][0] == label
    assert Counter(l for l in labels if l != "none")[label] / sum(l != "none" for l in labels) > 0.9


@pytest.mark.parametrize("fault,max_delay", [
    (FaultScenario.COMPRESSOR_STALL, 3),    # sudden: seen almost immediately
    (FaultScenario.BEARING_WEAR, 15),
    (FaultScenario.FUEL_NOZZLE_CLOG, 20),
])
def test_detection_latency(fault, max_delay):
    for seed in range(5):
        labels = run_scenario(fault, seed)
        assert next(i for i, l in enumerate(labels) if l != "none") <= max_delay


# ── RUL ──

def test_rul_requires_history_and_a_real_fault(rul_predictor):
    assert rul_predictor.predict(0.9, "bearing_wear") is None   # < 5 samples
    for _ in range(5):
        last = rul_predictor.predict(0.9, "bearing_wear")
    assert last is not None
    assert rul_predictor.predict(0.9, "none") is None


def test_rul_shrinks_as_anomaly_grows_and_respects_fault_base_hours():
    low, high = RULPredictor(), RULPredictor()
    for _ in range(6):
        a = low.predict(0.3, "bearing_wear")
        b = high.predict(0.9, "bearing_wear")
    assert a > b
    for fault, base in [("bearing_wear", 200), ("compressor_stall", 10), ("fuel_nozzle_clog", 80)]:
        p = RULPredictor()
        for _ in range(6):
            r = p.predict(0.5, fault)
        assert r == pytest.approx(base * 0.5, abs=0.1)


def test_rul_has_a_floor_of_half_an_hour():
    p = RULPredictor()
    for _ in range(6):
        r = p.predict(1.0, "compressor_stall")
    assert r == 0.5


def test_rul_unknown_fault_uses_default_base():
    p = RULPredictor()
    for _ in range(6):
        r = p.predict(0.5, "mystery_fault")
    assert r == pytest.approx(50.0, abs=0.1)


def test_rul_history_is_capped_at_100_samples():
    p = RULPredictor()
    for _ in range(250):
        p.predict(0.5, "bearing_wear")
    assert len(p._anomaly_history) == 100


def test_rul_is_none_when_recent_scores_are_mostly_healthy():
    """One high score after a run of near-zero scores is a blip, not a degradation trend."""
    p = RULPredictor()
    for _ in range(4):
        p.predict(0.0, "none")
    assert p.predict(0.25, "bearing_wear") is None   # last-5 average 0.05 <= 0.1
