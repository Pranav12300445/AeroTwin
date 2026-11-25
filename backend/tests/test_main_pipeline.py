"""process_telemetry (the per-tick pipeline) and simulator command handling."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app import main
from app.db.database import AssetHistory, TelemetryRecord
from app.main import handle_simulator_command, process_telemetry
from app.models.schemas import TelemetryReading
from app.simulator.engine import FaultScenario


def reading(**overrides):
    base = dict(timestamp=datetime(2026, 11, 23, 9, 0, 0, tzinfo=timezone.utc), egt=630.0, rpm_n1=73000.0,
                rpm_n2=77000.0, vibration=0.7, fuel_flow=0.45, oil_pressure=55.0, oil_temp=82.0)
    base.update(overrides)
    return TelemetryReading(**base)


@pytest.fixture
def broadcasts(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(main, "broadcast_to_clients", mock)
    return mock


async def events(bus, channel):
    return await bus.get_recent_events(channel)


# ── dashboard payload ──

async def test_normal_tick_payload_and_events(db, bus, broadcasts):
    await process_telemetry(reading())

    event_type, payload = broadcasts.await_args.args
    assert event_type == "telemetry"
    assert payload["engine_status"] == "normal"
    assert payload["is_anomaly"] is False and payload["fault_type"] == "none" and payload["rul_hours"] is None
    assert payload["timestamp"] == "2026-11-23T09:00:00+00:00"
    for key in ("twin_expected_egt", "twin_residual", "twin_health_factor", "twin_drift_detected",
                "anomaly_score", "top_anomaly_feature", "egt", "rpm_n1", "vibration", "oil_temp"):
        assert key in payload
    json.dumps(payload)  # must be JSON-serialisable for the WebSocket

    assert len(await events(bus, "telemetry.raw")) == 1
    assert await events(bus, "anomaly.detected") == []
    assert await events(bus, "fault.predicted") == []


async def test_normal_tick_is_stored_without_fault_and_without_asset_history(db, bus, broadcasts):
    await process_telemetry(reading())
    async with db() as s:
        rec = (await s.execute(select(TelemetryRecord))).scalar_one()
        assert (await s.execute(select(AssetHistory))).scalars().all() == []
    assert rec.engine_id == "engine-001" and rec.fault_type is None and rec.is_anomaly is False
    assert rec.egt == 630.0 and rec.anomaly_score == 0.0


# ── anomalies / faults ──

async def test_bearing_wear_signature_publishes_anomaly_and_fault_events(db, bus, broadcasts):
    await process_telemetry(reading(vibration=8.0, oil_temp=122.0, oil_pressure=35.0))

    payload = broadcasts.await_args.args[1]
    assert payload["is_anomaly"] is True
    assert payload["fault_type"] == "bearing_wear"
    assert payload["engine_status"] == "critical"            # score saturates -> critical

    anomaly = (await events(bus, "anomaly.detected"))[0]
    assert anomaly["agent"] == "telemetry_monitor"
    assert anomaly["data"]["fault_type"] == "bearing_wear"
    assert anomaly["data"]["top_feature"] == "vibration"
    assert "Anomaly detected" in anomaly["data"]["message"]

    fault = (await events(bus, "fault.predicted"))[0]
    assert fault["agent"] == "fault_predictor"
    assert fault["data"]["fault_type"] == "bearing_wear"
    assert fault["data"]["severity"] == "critical"
    assert fault["data"]["confidence"] == payload["anomaly_score"]


async def test_stall_signature_is_classified_as_compressor_stall(db, bus, broadcasts):
    await process_telemetry(reading(vibration=9.0, rpm_n1=52000.0, rpm_n2=58000.0, egt=745.0, fuel_flow=0.75))
    assert broadcasts.await_args.args[1]["fault_type"] == "compressor_stall"


async def test_anomaly_writes_fault_to_telemetry_and_asset_history(db, bus, broadcasts):
    await process_telemetry(reading(vibration=8.0))
    async with db() as s:
        rec = (await s.execute(select(TelemetryRecord))).scalar_one()
        hist = (await s.execute(select(AssetHistory))).scalar_one()
    assert rec.is_anomaly is True and rec.fault_type == "bearing_wear" and rec.anomaly_score == 1.0
    assert (hist.engine_id, hist.event_type, hist.fault_type, hist.resolved) == \
        ("engine-001", "fault_detected", "bearing_wear", False)
    assert "Anomaly score" in hist.description


@pytest.mark.parametrize("oil_temp,anomaly,status", [
    (82.0, False, "normal"),        # z=0     score 0.00
    (98.2, False, "warning"),       # z=2.7   score 0.45 -> warning without alarm
    (103.0, True, "warning"),       # z=3.5   score 0.58
    (112.0, True, "critical"),      # z=5.0   score 0.83
])
async def test_status_bands(db, bus, broadcasts, oil_temp, anomaly, status):
    await process_telemetry(reading(oil_temp=oil_temp))
    payload = broadcasts.await_args.args[1]
    assert (payload["is_anomaly"], payload["engine_status"]) == (anomaly, status)


async def test_rul_appears_once_the_fault_persists(db, bus, broadcasts):
    for _ in range(6):
        await process_telemetry(reading(vibration=8.0))
    payload = broadcasts.await_args.args[1]
    assert isinstance(payload["rul_hours"], float) and payload["rul_hours"] >= 0.5
    assert (await events(bus, "fault.predicted"))[-1]["data"]["rul_hours"] == payload["rul_hours"]


async def test_non_anomalous_reading_never_emits_fault_events(db, bus, broadcasts):
    for _ in range(5):
        await process_telemetry(reading(oil_temp=98.2))   # warning band but below alarm threshold
    assert await events(bus, "fault.predicted") == []
    assert await events(bus, "anomaly.detected") == []


# ── digital twin ──

async def test_twin_drift_publishes_twin_residual_event(db, bus, broadcasts, monkeypatch):
    twin = {"expected_egt": 600.0, "actual_egt": 650.0, "residual": 50.0, "residual_pct": 8.3,
            "health_factor": 0.93, "drift_detected": True}
    monkeypatch.setattr(main.digital_twin, "compute_residual", lambda r: twin)

    await process_telemetry(reading())

    ev = (await events(bus, "twin.residual"))[0]
    assert ev["agent"] == "digital_twin_sync"
    assert ev["data"]["residual"] == 50.0
    assert "Twin drift detected" in ev["data"]["message"] and "0.930" in ev["data"]["message"]
    payload = broadcasts.await_args.args[1]
    assert payload["twin_drift_detected"] is True and payload["twin_health_factor"] == 0.93


async def test_no_twin_event_without_drift(db, bus, broadcasts):
    await process_telemetry(reading())
    assert await events(bus, "twin.residual") == []


# ── resilience ──

async def test_database_failure_is_swallowed_and_broadcast_still_happens(bus, broadcasts, monkeypatch):
    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "get_session_factory", broken)
    await process_telemetry(reading(vibration=8.0))      # must not raise
    broadcasts.assert_awaited_once()
    assert len(await events(bus, "fault.predicted")) == 1


# ── simulator commands ──

@pytest.mark.parametrize("scenario", [s.value for s in FaultScenario])
async def test_inject_fault_command_sets_simulator_scenario(scenario):
    await handle_simulator_command({"data": {"action": "inject_fault", "scenario": scenario}})
    assert main.simulator.active_fault.value == scenario


async def test_invalid_scenario_is_ignored():
    main.simulator.inject_fault(FaultScenario.BEARING_WEAR)
    await handle_simulator_command({"data": {"action": "inject_fault", "scenario": "meteor_strike"}})
    assert main.simulator.active_fault == FaultScenario.BEARING_WEAR


async def test_inject_without_scenario_clears_fault():
    main.simulator.inject_fault(FaultScenario.BEARING_WEAR)
    await handle_simulator_command({"data": {"action": "inject_fault"}})
    assert main.simulator.active_fault == FaultScenario.NONE


async def test_reset_command_clears_fault_and_resets_twin_health():
    main.simulator.inject_fault(FaultScenario.COMPRESSOR_STALL)
    main.digital_twin._health_factor = 0.62
    main.digital_twin._residual_history.extend([50.0] * 10)

    await handle_simulator_command({"data": {"action": "reset"}})

    assert main.simulator.active_fault == FaultScenario.NONE
    assert main.digital_twin.health_factor == 1.0
    assert main.digital_twin._residual_history == []


@pytest.mark.parametrize("event", [{}, {"data": {}}, {"data": {"action": "self_destruct"}}])
async def test_unknown_or_empty_commands_are_ignored(event):
    main.simulator.inject_fault(FaultScenario.FUEL_NOZZLE_CLOG)
    await handle_simulator_command(event)
    assert main.simulator.active_fault == FaultScenario.FUEL_NOZZLE_CLOG
