"""Simulator -> twin -> detector -> classifier -> event bus -> DB -> WebSocket, with the real components."""

import json

import pytest
from sqlalchemy import func, select

from app import main
from app.db.database import AssetHistory, TelemetryRecord
from app.main import handle_simulator_command
from app.simulator.engine import FaultScenario

pytestmark = pytest.mark.integration


async def count(db, model):
    async with db() as s:
        return (await s.execute(select(func.count()).select_from(model))).scalar_one()


async def test_healthy_engine_runs_clean_end_to_end(db, bus, run_ticks, ws_recorder):
    payloads = await run_ticks(60)

    assert {p["engine_status"] for p in payloads} == {"normal"}
    assert not any(p["is_anomaly"] or p["twin_drift_detected"] for p in payloads)
    assert all(p["fault_type"] == "none" and p["rul_hours"] is None for p in payloads)
    assert payloads[-1]["twin_health_factor"] >= 0.995

    assert await count(db, TelemetryRecord) == 60
    assert await count(db, AssetHistory) == 0
    assert len(await bus.get_recent_events("telemetry.raw", count=100)) == 60
    for channel in ("anomaly.detected", "fault.predicted", "maintenance.recommended"):
        assert await bus.get_recent_events(channel) == []
    assert ws_recorder.messages("maintenance") == []


@pytest.mark.parametrize("fault,label,duration", [
    (FaultScenario.BEARING_WEAR, "bearing_wear", 40),
    (FaultScenario.COMPRESSOR_STALL, "compressor_stall", 15),
    (FaultScenario.FUEL_NOZZLE_CLOG, "fuel_nozzle_clog", 45),
])
async def test_each_demo_scenario_is_detected_classified_and_recorded(db, bus, run_ticks, fault, label, duration):
    await run_ticks(20)
    payloads = await run_ticks(duration, fault=fault)

    flagged = [p for p in payloads if p["is_anomaly"]]
    assert flagged, "the fault was never detected"
    assert payloads[-1]["is_anomaly"] and payloads[-1]["engine_status"] in {"warning", "critical"}
    # sustained, and the label settles on the right fault
    assert [p["fault_type"] for p in payloads[-8:]] == [label] * 8
    assert any(isinstance(p["rul_hours"], float) for p in payloads)

    predicted = await bus.get_recent_events("fault.predicted", count=500)
    assert predicted and predicted[-1]["data"]["fault_type"] == label
    assert predicted[-1]["agent"] == "fault_predictor"
    assert len(await bus.get_recent_events("anomaly.detected", count=500)) >= len(predicted)

    async with db() as s:
        stored = (await s.execute(select(TelemetryRecord).where(TelemetryRecord.is_anomaly))).scalars().all()
        history = (await s.execute(select(AssetHistory))).scalars().all()
    assert len(stored) == len(flagged)
    assert history and history[-1].fault_type == label


async def test_stall_is_detected_within_seconds(run_ticks):
    await run_ticks(20)
    payloads = await run_ticks(10, fault=FaultScenario.COMPRESSOR_STALL)
    first = next(i for i, p in enumerate(payloads) if p["is_anomaly"])
    assert first <= 3
    assert payloads[-1]["engine_status"] == "critical"


async def test_bearing_wear_escalates_from_warning_to_critical(run_ticks):
    await run_ticks(20)
    payloads = await run_ticks(60, fault=FaultScenario.BEARING_WEAR)
    statuses = [p["engine_status"] for p in payloads]
    assert "normal" in statuses[:3] and statuses[-1] == "critical"
    assert payloads[-1]["vibration"] > payloads[0]["vibration"] + 5
    rul = [p["rul_hours"] for p in payloads if p["rul_hours"] is not None]
    assert rul[-1] < rul[0], "remaining useful life should shrink as the bearing degrades"


async def test_reset_command_brings_the_engine_back_to_normal(run_ticks):
    await run_ticks(20)
    await run_ticks(40, fault=FaultScenario.BEARING_WEAR)
    assert main.simulator.active_fault == FaultScenario.BEARING_WEAR

    await handle_simulator_command({"data": {"action": "reset"}})
    after = await run_ticks(20)

    assert main.simulator.active_fault == FaultScenario.NONE
    assert after[-1]["engine_status"] == "normal" and after[-1]["fault_type"] == "none"
    assert not any(p["is_anomaly"] for p in after[-10:])
    assert main.digital_twin.health_factor == 1.0


async def test_every_agent_event_is_mirrored_to_the_activity_feed(bus, run_ticks):
    feed = bus._redis.pubsub()
    await feed.subscribe("agent.activity")
    await feed.get_message(timeout=0.1)

    await run_ticks(10)
    await run_ticks(20, fault=FaultScenario.COMPRESSOR_STALL)

    seen = []
    while (msg := await feed.get_message(ignore_subscribe_messages=True, timeout=0.05)):
        seen.append(json.loads(msg["data"]))
    pairs = {(a["agent"], a["event"]) for a in seen}
    assert ("telemetry_monitor", "telemetry.raw") in pairs
    assert ("telemetry_monitor", "anomaly.detected") in pairs
    assert ("fault_predictor", "fault.predicted") in pairs
    assert all(a["summary"] for a in seen)


async def test_sustained_run_keeps_database_and_stream_consistent(db, bus, run_ticks):
    await run_ticks(100)
    assert await count(db, TelemetryRecord) == 100
    assert len(await bus.get_recent_events("telemetry.raw", count=500)) == 100
