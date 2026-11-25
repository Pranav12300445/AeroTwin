"""Real WebSocket handshakes against the running app (Starlette TestClient runs the lifespan in its
own loop, like uvicorn). Only external services are replaced: SQLite for TimescaleDB, fakeredis for
Redis, and stubs for the RAG index and the Groq call."""

import json

import fakeredis
import fakeredis.aioredis
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import event_bus, main
from app.agents import coordinator
from app.auth.auth import create_access_token
from app.config import Settings
from app.db import database
from app.simulator.engine import FaultScenario
from tests.conftest import StubRAG

pytestmark = pytest.mark.integration


@pytest.fixture
def running_app(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, simulator_enabled=True, simulator_interval_ms=20,
                        database_url=f"sqlite+aiosqlite:///{tmp_path / 'e2e.db'}")
    server = fakeredis.FakeServer()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_session_factory", None)
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(event_bus, "_event_bus", None)
    monkeypatch.setattr(event_bus.aioredis, "from_url",
                        lambda url, **kw: fakeredis.aioredis.FakeRedis(server=server, decode_responses=True))

    async def llm(system, user):
        return json.dumps({"summary": "Inspect compressor.", "urgency": "emergency", "steps": ["Idle"],
                           "estimated_downtime": "4 h", "safety_note": ""})

    monkeypatch.setattr(coordinator, "get_rag", lambda: StubRAG())
    monkeypatch.setattr(coordinator, "ask_llm", llm)

    with TestClient(main.app) as client:
        yield client


def ws_url(role_name, role):
    return f"/ws/telemetry?token={create_access_token(role_name, role)}"


def test_handshake_without_token_is_refused(running_app):
    with pytest.raises(WebSocketDisconnect):
        with running_app.websocket_connect("/ws/telemetry"):
            pass


def test_handshake_with_bad_token_is_refused(running_app):
    with pytest.raises(WebSocketDisconnect):
        with running_app.websocket_connect("/ws/telemetry?token=not-a-jwt"):
            pass


def test_authenticated_client_receives_live_telemetry(running_app):
    with running_app.websocket_connect(ws_url("operator", "operator")) as ws:
        msgs = [ws.receive_json() for _ in range(5)]
    telemetry = [m for m in msgs if m["type"] == "telemetry"]
    assert telemetry
    d = telemetry[0]["data"]
    assert d["engine_status"] == "normal" and d["engine_id"] == "engine-001"
    assert 500 < d["egt"] < 760 and 0 <= d["anomaly_score"] <= 1


def test_login_over_http_then_stream_over_websocket(running_app):
    """What the dashboard does: POST /login, then open the socket with the returned token."""
    login = running_app.post("/api/auth/login", data={"username": "engineer", "password": "engineer123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    with running_app.websocket_connect(f"/ws/telemetry?token={token}") as ws:
        assert ws.receive_json()["type"] in {"telemetry", "agent_activity", "maintenance"}


def test_engineer_injects_fault_over_socket_and_gets_maintenance_advice(running_app):
    with running_app.websocket_connect(ws_url("engineer", "maintenance_engineer")) as ws:
        ws.send_text(json.dumps({"action": "inject_fault", "scenario": "compressor_stall"}))

        poked, saw_fault, recommendation = False, False, None
        for _ in range(600):
            msg = ws.receive_json()
            if not poked and main.simulator.active_fault == FaultScenario.COMPRESSOR_STALL:
                main.simulator._fault_start_time -= 60    # skip the 5 s ramp
                poked = True
            if msg["type"] == "telemetry" and msg["data"]["fault_type"] == "compressor_stall":
                saw_fault = True
            if msg["type"] == "maintenance":
                recommendation = msg["data"]
                break

    assert poked and saw_fault
    assert recommendation["fault_type"] == "compressor_stall"
    assert recommendation["llm_enhanced"] is True and recommendation["priority"] == "emergency"


def test_operator_socket_commands_do_not_move_the_engine(running_app):
    with running_app.websocket_connect(ws_url("operator", "operator")) as ws:
        ws.send_text(json.dumps({"action": "inject_fault", "scenario": "bearing_wear"}))
        for _ in range(40):          # ~0.8 s of stream: plenty for the command to have been applied
            ws.receive_json()
    assert main.simulator.active_fault == FaultScenario.NONE


def test_two_clients_both_receive_the_stream_and_disconnects_are_survived(running_app):
    a = running_app.websocket_connect(ws_url("operator", "operator"))
    b = running_app.websocket_connect(ws_url("admin", "admin"))
    wa, wb = a.__enter__(), b.__enter__()
    assert wa.receive_json() and wb.receive_json()
    a.__exit__(None, None, None)                       # one client leaves...
    assert wb.receive_json() and wb.receive_json()     # ...the other keeps streaming
    b.__exit__(None, None, None)
