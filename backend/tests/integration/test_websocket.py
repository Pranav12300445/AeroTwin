"""WebSocket endpoint + broadcast fan-out, driven with a fake socket against the real handler."""

import json
from datetime import datetime, timezone

import pytest

from app.api import routes
from app.auth.auth import create_access_token

pytestmark = pytest.mark.integration

POLICY_VIOLATION = 1008


def token(role_name):
    role = {"operator": "operator", "engineer": "maintenance_engineer", "admin": "admin"}[role_name]
    return create_access_token(role_name, role)


async def connect(fake_ws, role, *messages):
    sock = fake_ws([json.dumps(m) if not isinstance(m, str) else m for m in messages])
    await routes.telemetry_ws(sock, token=token(role))
    return sock


# ── authentication ──

@pytest.mark.parametrize("bad", ["", "garbage", "a.b.c"])
async def test_connection_without_valid_token_is_rejected(fake_ws, bad):
    sock = fake_ws()
    await routes.telemetry_ws(sock, token=bad)
    assert sock.close_code == POLICY_VIOLATION
    assert sock.accepted is False
    assert sock not in routes._ws_connections


async def test_expired_token_is_rejected(fake_ws, monkeypatch):
    from app.auth import auth
    from app.config import Settings
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(access_token_expire_minutes=-1, _env_file=None))
    expired = create_access_token("admin", "admin")
    monkeypatch.undo()
    sock = fake_ws()
    await routes.telemetry_ws(sock, token=expired)
    assert sock.close_code == POLICY_VIOLATION and not sock.accepted


async def test_valid_token_is_accepted_registered_and_cleaned_up_on_disconnect(fake_ws):
    seen_during = []

    class Spy(fake_ws):
        async def receive_text(self):
            seen_during.append(self in routes._ws_connections)
            return await super().receive_text()

    sock = Spy()
    await routes.telemetry_ws(sock, token=token("operator"))
    assert sock.accepted is True
    assert seen_during == [True]
    assert sock not in routes._ws_connections


# ── commands: RBAC ──

@pytest.mark.parametrize("role", ["engineer", "admin"])
async def test_engineer_and_admin_can_inject_faults_over_the_socket(fake_ws, bus, role):
    await connect(fake_ws, role, {"action": "inject_fault", "scenario": "compressor_stall"})
    cmds = await bus.get_recent_events("simulator.command")
    assert [c["data"] for c in cmds] == [{"action": "inject_fault", "scenario": "compressor_stall"}]
    assert cmds[0]["agent"] == "dashboard"


async def test_operator_cannot_inject_faults_over_the_socket(fake_ws, bus):
    """Regression: the socket used to accept commands from anyone, bypassing the REST RBAC."""
    sock = await connect(fake_ws, "operator", {"action": "inject_fault", "scenario": "compressor_stall"})
    assert sock.accepted is True            # may watch the stream...
    assert await bus.get_recent_events("simulator.command") == []   # ...but not control the engine


async def test_scenario_defaults_to_none(fake_ws, bus):
    await connect(fake_ws, "engineer", {"action": "inject_fault"})
    assert (await bus.get_recent_events("simulator.command"))[0]["data"]["scenario"] == "none"


@pytest.mark.parametrize("junk", ["not json", "[1, 2]", "42", "null", '{"action": "format_disk"}', "{}"])
async def test_malformed_or_unknown_commands_are_ignored_without_dropping_the_connection(fake_ws, bus, junk):
    sock = await connect(fake_ws, "admin", junk, {"action": "inject_fault", "scenario": "bearing_wear"})
    # the junk frame was skipped and the loop kept reading: the valid command after it was processed
    assert len(await bus.get_recent_events("simulator.command")) == 1
    assert sock.incoming == []


# ── broadcast ──

async def test_broadcast_delivers_typed_json_to_every_client(fake_ws):
    a, b = fake_ws(), fake_ws()
    routes._ws_connections.update({a, b})
    await routes.broadcast_to_clients("telemetry", {"egt": 630.5})
    for sock in (a, b):
        assert [json.loads(m) for m in sock.sent] == [{"type": "telemetry", "data": {"egt": 630.5}}]


async def test_broadcast_without_clients_is_a_noop():
    await routes.broadcast_to_clients("telemetry", {"x": 1})   # used to raise UnboundLocalError


async def test_dead_client_is_dropped_and_others_still_receive(fake_ws):
    """Regression: `_ws_connections -= dead` rebound the global, so *every* broadcast raised."""
    good, dead = fake_ws(), fake_ws()

    async def boom(message):
        raise ConnectionResetError()

    dead.send_text = boom
    routes._ws_connections.update({good, dead})

    await routes.broadcast_to_clients("telemetry", {"n": 1})
    assert dead not in routes._ws_connections and good in routes._ws_connections
    await routes.broadcast_to_clients("telemetry", {"n": 2})
    assert [json.loads(m)["data"]["n"] for m in good.sent] == [1, 2]


async def test_broadcast_serialises_datetimes(fake_ws):
    sock = fake_ws()
    routes._ws_connections.add(sock)
    await routes.broadcast_to_clients("x", {"at": datetime(2026, 11, 23, tzinfo=timezone.utc)})
    assert "2026-11-23" in json.loads(sock.sent[0])["data"]["at"]
