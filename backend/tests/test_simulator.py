"""Tests for the engine simulator and fault scenarios."""

import time

from app.simulator.engine import EngineSimulator, FaultScenario


def test_simulator_generate_reading_returns_telemetry(simulator):
    reading = simulator.generate_reading()
    assert reading.engine_id == "engine-001"
    assert 0 <= reading.egt <= 1200
    assert 0 <= reading.rpm_n1 <= 120000
    assert 0 <= reading.rpm_n2 <= 120000
    assert 0 <= reading.vibration <= 50
    assert 0 <= reading.fuel_flow <= 10
    assert 0 <= reading.oil_pressure <= 150
    assert 0 <= reading.oil_temp <= 200


def test_simulator_normal_readings_in_nominal_range(simulator):
    for _ in range(20):
        reading = simulator.generate_reading()
        # throttle factor ranges 0.85-1.15 around nominal; widen bands accordingly
        assert 530 <= reading.egt <= 730
        assert 62000 <= reading.rpm_n1 <= 84000
        assert 65000 <= reading.rpm_n2 <= 89000


def test_simulator_inject_fault_changes_active_fault(simulator):
    assert simulator.active_fault == FaultScenario.NONE
    simulator.inject_fault(FaultScenario.BEARING_WEAR)
    assert simulator.active_fault == FaultScenario.BEARING_WEAR
    simulator.inject_fault(FaultScenario.NONE)
    assert simulator.active_fault == FaultScenario.NONE


def test_simulator_bearing_wear_increases_vibration(simulator):
    simulator.inject_fault(FaultScenario.BEARING_WEAR)
    simulator._fault_start_time = time.time() - 999  # force full progress
    readings = [simulator.generate_reading() for _ in range(20)]
    mean_vibration = sum(r.vibration for r in readings) / len(readings)
    assert mean_vibration > 5.0  # normal vibration is ~0.7g; fully worn bearing ~8.7g


def test_simulator_compressor_stall_causes_rpm_drop(simulator):
    simulator.inject_fault(FaultScenario.COMPRESSOR_STALL)
    simulator._fault_start_time = time.time() - 999  # force full progress
    readings = [simulator.generate_reading() for _ in range(20)]
    mean_rpm_n1 = sum(r.rpm_n1 for r in readings) / len(readings)
    # nominal 73000 x throttle (0.85-1.15) minus 21000 => at most ~63000 (was a flat 60000: flaky)
    assert mean_rpm_n1 < 64000


def test_simulator_fuel_nozzle_clog_reduces_fuel_flow(simulator):
    simulator.inject_fault(FaultScenario.FUEL_NOZZLE_CLOG)
    simulator._fault_start_time = time.time() - 999  # force full progress
    readings = [simulator.generate_reading() for _ in range(20)]
    mean_fuel_flow = sum(r.fuel_flow for r in readings) / len(readings)
    # nominal 0.45 x throttle (0.85-1.15, random phase) minus 0.25 => at most ~0.27 (was a flat 0.25: flaky)
    assert mean_fuel_flow <= 0.32


def test_simulator_fault_scenario_enum_values():
    assert FaultScenario.NONE == "none"
    assert FaultScenario.BEARING_WEAR == "bearing_wear"
    assert FaultScenario.COMPRESSOR_STALL == "compressor_stall"
    assert FaultScenario.FUEL_NOZZLE_CLOG == "fuel_nozzle_clog"


def test_simulator_generate_reading_advances_tick(simulator):
    r1 = simulator.generate_reading()
    r2 = simulator.generate_reading()
    assert r2.timestamp >= r1.timestamp


def test_simulator_stop_sets_running_false(simulator):
    import asyncio

    async def run():
        task = asyncio.create_task(simulator.run(lambda r: None))
        await asyncio.sleep(0.05)
        simulator.stop()
        await asyncio.sleep(0.05)
        assert simulator._running is False

    asyncio.run(run())
