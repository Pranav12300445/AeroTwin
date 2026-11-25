"""The full application lifespan: startup wiring, simulator task, event-bus listener, agents and
shutdown, all running together inside one event loop (DB=SQLite, Redis=fakeredis, RAG/LLM stubbed)."""

import asyncio
import json

import pytest

from app import main
from app.api import routes
from app.config import Settings
from app.simulator.engine import FaultScenario
from tests.conftest import wait_for

pytestmark = pytest.mark.integration

LLM_JSON = json.dumps({
    "summary": "Compressor stall detected; shut down and borescope the compressor.",
    "urgency": "emergency",
    "steps": ["Throttle to idle", "Borescope each stage"],
    "estimated_downtime": "4-6 hours",
    "safety_note": "Do not restart until inspected.",
})


@pytest.fixture
def lifespan_env(monkeypatch, db, bus, stub_rag, stub_llm):
    """Fast simulator (20 ms ticks) + stubbed RAG/LLM; returns a helper to run the real lifespan."""
    monkeypatch.setattr(main, "get_settings",
                        lambda: Settings(_env_file=None, simulator_enabled=True, simulator_interval_ms=20))

    class Env:
        pass

    env = Env()
    env.llm, env.rag = stub_llm, stub_rag
    env.run = lambda: main.app.router.lifespan_context(main.app)
    return env


async def telemetry_flowing(ws):
    return len(ws.messages("telemetry")) >= 3


async def test_startup_seeds_users_starts_simulator_and_streams_telemetry(lifespan_env, ws_recorder, db):
    from sqlalchemy import select
    from app.db.database import User

    async with lifespan_env.run():
        await wait_for(lambda: len(ws_recorder.messages("telemetry")) >= 5)
        assert main.simulator._running is True
        async with db() as s:
            users = {u.username: u.role for u in (await s.execute(select(User))).scalars()}
    assert users == {"operator": "operator", "engineer": "maintenance_engineer", "admin": "admin"}
    assert main.simulator._running is False   # shutdown stopped it

    first = ws_recorder.messages("telemetry")[0]["data"]
    assert first["engine_status"] == "normal" and first["engine_id"] == "engine-001"


async def test_simulator_can_be_disabled_by_config(lifespan_env, monkeypatch, ws_recorder):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, simulator_enabled=False))
    async with lifespan_env.run():
        await asyncio.sleep(0.2)
    assert ws_recorder.messages("telemetry") == []


async def test_injected_fault_flows_through_every_agent_to_the_dashboard(lifespan_env, client, auth, ws_recorder, bus):
    """API -> bus -> simulator -> twin/detector -> fault.predicted -> planner (RAG+LLM) -> maintenance.recommended -> WS."""
    lifespan_env.llm.response = LLM_JSON

    async with lifespan_env.run():
        await wait_for(lambda: len(ws_recorder.messages("telemetry")) >= 3)

        resp = await client.post("/api/simulator/fault/compressor_stall", headers=auth["engineer"])
        assert resp.status_code == 200
        await wait_for(lambda: main.simulator.active_fault == FaultScenario.COMPRESSOR_STALL)
        main.simulator._fault_start_time -= 60    # skip the 5 s ramp: stall is fully developed

        rec = (await wait_for(lambda: ws_recorder.messages("maintenance"), timeout=10))[0]["data"]
        # the planner's activity-feed entry is a separate pub/sub delivery: wait for it too
        await wait_for(lambda: any(a["data"]["agent"] == "maintenance_planner"
                                   for a in ws_recorder.messages("agent_activity")))
        telemetry = ws_recorder.messages("telemetry")

    assert rec["fault_type"] == "compressor_stall"
    assert rec["llm_enhanced"] is True and rec["priority"] == "emergency"
    assert rec["steps"] == ["Throttle to idle", "Borescope each stage"]
    assert rec["source_documents"] == ["bearing_inspection.md", "routine_health_check.md"]  # from the stub RAG
    assert lifespan_env.rag.calls[0] == "compressor_stall"

    assert any(m["data"]["fault_type"] == "compressor_stall" and m["data"]["engine_status"] == "critical"
               for m in telemetry)
    activity = ws_recorder.messages("agent_activity")
    agents = {a["data"]["agent"] for a in activity}
    assert {"api", "fault_predictor", "maintenance_planner"} <= agents


async def test_only_one_recommendation_per_fault_despite_one_hz_fault_events(lifespan_env, ws_recorder):
    """fault.predicted fires every anomalous tick; the planner must not call the LLM for each one."""
    async with lifespan_env.run():
        await wait_for(lambda: len(ws_recorder.messages("telemetry")) >= 3)
        await main.handle_simulator_command({"data": {"action": "inject_fault", "scenario": "compressor_stall"}})
        main.simulator._fault_start_time -= 60
        await wait_for(lambda: ws_recorder.messages("maintenance"), timeout=10)
        before = len(ws_recorder.messages("telemetry"))
        await wait_for(lambda: len(ws_recorder.messages("telemetry")) >= before + 30)

    assert len(lifespan_env.llm.prompts) <= 2       # (fault, severity) pairs seen, not ~30 ticks
    assert len(ws_recorder.messages("maintenance")) <= 2


async def test_llm_unavailable_still_gives_a_recommendation(lifespan_env, ws_recorder):
    lifespan_env.llm.response = ""   # no key / Groq down
    async with lifespan_env.run():
        await wait_for(lambda: len(ws_recorder.messages("telemetry")) >= 3)
        await main.handle_simulator_command({"data": {"action": "inject_fault", "scenario": "bearing_wear"}})
        main.simulator._fault_start_time -= 120
        rec = (await wait_for(lambda: ws_recorder.messages("maintenance"), timeout=10))[0]["data"]
    assert rec["llm_enhanced"] is False
    assert rec["fault_type"] == "bearing_wear" and rec["procedure_summary"]


async def test_reset_through_the_api_clears_the_fault(lifespan_env, client, auth, ws_recorder):
    async with lifespan_env.run():
        await wait_for(lambda: len(ws_recorder.messages("telemetry")) >= 3)
        await client.post("/api/simulator/fault/bearing_wear", headers=auth["admin"])
        await wait_for(lambda: main.simulator.active_fault == FaultScenario.BEARING_WEAR)
        await client.post("/api/simulator/reset", headers=auth["admin"])
        await wait_for(lambda: main.simulator.active_fault == FaultScenario.NONE)
        assert (await client.get("/")).json()["active_fault"] == "none"


async def test_shutdown_stops_background_tasks_cleanly(lifespan_env, bus):
    async with lifespan_env.run():
        await asyncio.sleep(0.1)
    assert bus._running is False
    assert main.simulator._running is False
