"""Simulator run loop, fault timing (fake clock), physical limits, and twin calibration."""

import asyncio
import random

import pytest

from app.models.schemas import TelemetryReading
from app.simulator.engine import EngineSimulator, FaultScenario
from app.twin.digital_twin import DigitalTwin


# ── run loop ──

async def test_run_calls_back_with_readings_until_stopped():
    sim = EngineSimulator(interval_ms=5)
    got = []

    async def cb(reading):
        got.append(reading)
        if len(got) == 3:
            sim.stop()

    await asyncio.wait_for(sim.run(cb), timeout=2)
    assert len(got) == 3 and all(isinstance(r, TelemetryReading) for r in got)
    assert sim._running is False


async def test_callback_failure_does_not_kill_the_stream():
    """Regression: an exception in the pipeline used to end the simulator task silently."""
    sim = EngineSimulator(interval_ms=5)
    calls = []

    async def cb(reading):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("pipeline blew up")
        if len(calls) == 4:
            sim.stop()

    await asyncio.wait_for(sim.run(cb), timeout=2)
    assert len(calls) == 4


# ── fault progress (fake clock) ──

@pytest.mark.parametrize("fault,duration", [
    (FaultScenario.BEARING_WEAR, 60.0),
    (FaultScenario.COMPRESSOR_STALL, 5.0),
    (FaultScenario.FUEL_NOZZLE_CLOG, 30.0),
])
def test_fault_progress_is_linear_and_capped(fake_clock, fault, duration):
    sim = EngineSimulator()
    sim.inject_fault(fault)
    assert sim._get_fault_progress() == 0.0
    fake_clock.advance(duration / 2)
    assert sim._get_fault_progress() == pytest.approx(0.5)
    fake_clock.advance(duration * 10)
    assert sim._get_fault_progress() == 1.0


def test_no_fault_means_no_progress(fake_clock):
    sim = EngineSimulator()
    fake_clock.advance(1000)
    assert sim._get_fault_progress() == 0.0


def test_reinjecting_restarts_the_ramp(fake_clock):
    sim = EngineSimulator()
    sim.inject_fault(FaultScenario.BEARING_WEAR)
    fake_clock.advance(30)
    sim.inject_fault(FaultScenario.BEARING_WEAR)
    assert sim._get_fault_progress() == 0.0


def test_clearing_fault_returns_readings_to_normal(fake_clock):
    random.seed(7)
    sim = EngineSimulator()
    sim.inject_fault(FaultScenario.BEARING_WEAR)
    fake_clock.advance(100)
    assert sim.generate_reading().vibration > 5
    sim.inject_fault(FaultScenario.NONE)
    assert sim._fault_start_time is None
    assert all(sim.generate_reading().vibration < 2 for _ in range(20))


@pytest.mark.parametrize("fault", list(FaultScenario))
def test_every_scenario_always_yields_valid_clamped_readings(fake_clock, fault):
    """The pydantic bounds (e.g. vibration <= 50 g) must never be violated, at any fault stage."""
    random.seed(11)
    sim = EngineSimulator()
    sim.inject_fault(fault)
    for _ in range(150):
        fake_clock.advance(1)
        r = sim.generate_reading()      # raises ValidationError if the simulator exceeds a limit
        assert 0 <= r.egt <= 1200 and 0 <= r.vibration <= 50 and 0 <= r.fuel_flow <= 10


def test_stall_has_surge_then_collapse(fake_clock):
    random.seed(3)
    sim = EngineSimulator()
    sim.inject_fault(FaultScenario.COMPRESSOR_STALL)
    fake_clock.advance(1.0)   # progress 0.2: surge phase, vibration spike
    surge = sim.generate_reading()
    fake_clock.advance(10.0)  # fully developed: RPM collapsed
    stalled = sim.generate_reading()
    assert surge.vibration > 2.5
    assert stalled.rpm_n1 < surge.rpm_n1 - 10000


def test_readings_carry_engine_id():
    assert EngineSimulator(engine_id="uav-7").generate_reading().engine_id == "uav-7"


# ── digital twin calibration (regression: miscalibration made a healthy engine look degraded) ──

def healthy(sim, twin, n=300):
    residuals = []
    for _ in range(n):
        residuals.append(twin.compute_residual(sim.generate_reading())["residual"])
    return residuals


def test_twin_predicts_nominal_egt_for_nominal_inputs():
    expected = DigitalTwin().predict_egt(TelemetryReading(
        egt=630, rpm_n1=73000, rpm_n2=77000, vibration=0.7, fuel_flow=0.45,
        oil_pressure=55, oil_temp=82, oat=25, altitude=500))
    assert expected == pytest.approx(630, abs=5)


@pytest.mark.parametrize("seed", range(5))
def test_healthy_engine_keeps_full_twin_health_and_no_drift(seed, fake_clock):
    random.seed(seed)
    sim, twin = EngineSimulator(), DigitalTwin()
    drift = 0
    for _ in range(300):
        fake_clock.advance(1)
        drift += twin.compute_residual(sim.generate_reading())["drift_detected"]
    assert twin.health_factor >= 0.995
    assert drift <= 2


@pytest.mark.parametrize("fault", [FaultScenario.FUEL_NOZZLE_CLOG, FaultScenario.COMPRESSOR_STALL])
def test_egt_affecting_faults_show_up_as_twin_drift_and_health_loss(fault, fake_clock):
    random.seed(5)
    sim, twin = EngineSimulator(), DigitalTwin()
    for _ in range(40):
        fake_clock.advance(1)
        twin.compute_residual(sim.generate_reading())
    sim.inject_fault(fault)
    drift = 0
    for _ in range(70):
        fake_clock.advance(1)
        drift += twin.compute_residual(sim.generate_reading())["drift_detected"]
    assert drift >= 5
    assert twin.health_factor < 0.99


def test_twin_drift_needs_an_absolute_offset_not_just_a_ratio():
    """A tiny residual that grows 3x is noise, not drift."""
    twin = DigitalTwin()
    reading = TelemetryReading(egt=630, rpm_n1=73000, rpm_n2=77000, vibration=0.7, fuel_flow=0.45,
                               oil_pressure=55, oil_temp=82, oat=25, altitude=500)
    twin._residual_history = [1.0] * 10 + [3.0] * 9
    assert twin.compute_residual(reading)["drift_detected"] is False
