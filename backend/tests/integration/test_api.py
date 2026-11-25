"""REST API against the real app: auth, RBAC, telemetry history, simulator control."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import delete

from app.auth import auth as auth_module
from app.config import Settings
from app.db.database import User
from app.simulator.engine import FaultScenario

pytestmark = pytest.mark.integration


# ── service info ──

async def test_root_and_health(client):
    root = (await client.get("/")).json()
    assert root["app"] == "AeroTwin" and root["status"] == "running" and root["active_fault"] == "none"
    assert (await client.get("/api/health")).json() == {"status": "healthy"}


async def test_openapi_documents_every_route(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    for p in ["/api/auth/login", "/api/auth/me", "/api/telemetry/history", "/api/telemetry/asset-history",
              "/api/simulator/fault/{scenario}", "/api/simulator/reset", "/api/health"]:
        assert p in paths


# ── login / me ──

@pytest.mark.parametrize("username,role", [
    ("operator", "operator"), ("engineer", "maintenance_engineer"), ("admin", "admin"),
])
async def test_login_then_me_for_each_role(client, username, role):
    resp = await client.post("/api/auth/login", data={"username": username, "password": f"{username}123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer" and body["role"] == role

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json() == {"username": username, "role": role}


@pytest.mark.parametrize("data", [
    {"username": "admin", "password": "wrong"},
    {"username": "nobody", "password": "admin123"},
])
async def test_bad_credentials_are_401(client, data):
    resp = await client.post("/api/auth/login", data=data)
    assert resp.status_code == 401 and resp.json()["detail"] == "Invalid credentials"


async def test_login_rejects_malformed_requests(client):
    assert (await client.post("/api/auth/login", data={"username": "admin"})).status_code == 422
    # empty password: 422 (newer FastAPI form validation) or 401 (0.115.x); never a success
    assert (await client.post("/api/auth/login", data={"username": "admin", "password": ""})).status_code in (401, 422)
    assert (await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})).status_code == 422


async def test_failed_logins_do_not_reveal_whether_the_user_exists(client):
    a = await client.post("/api/auth/login", data={"username": "admin", "password": "bad"})
    b = await client.post("/api/auth/login", data={"username": "ghost", "password": "bad"})
    assert a.json() == b.json()


# ── authentication on protected routes ──

PROTECTED = [
    ("GET", "/api/auth/me"), ("GET", "/api/telemetry/history"), ("GET", "/api/telemetry/asset-history"),
    ("POST", "/api/simulator/fault/bearing_wear"), ("POST", "/api/simulator/reset"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_protected_routes_require_a_token(client, method, path):
    resp = await client.request(method, path)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_protected_routes_reject_garbage_tokens(client, method, path):
    assert (await client.request(method, path, headers={"Authorization": "Bearer nonsense"})).status_code == 401


async def test_expired_token_is_rejected(client, monkeypatch):
    monkeypatch.setattr(auth_module, "get_settings", lambda: Settings(access_token_expire_minutes=-1, _env_file=None))
    token = auth_module.create_access_token("admin", "admin")
    monkeypatch.undo()  # validation must use real settings
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_forged_token_with_wrong_secret_is_rejected(client):
    forged = jwt.encode({"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        "attacker-secret", algorithm="HS256")
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})).status_code == 401


async def test_token_of_a_deleted_user_stops_working(client, auth, seeded_db):
    async with seeded_db() as s:
        await s.execute(delete(User).where(User.username == "operator"))
        await s.commit()
    assert (await client.get("/api/auth/me", headers=auth["operator"])).status_code == 401


async def test_role_comes_from_the_database_not_the_token(client, auth, seeded_db):
    """An operator can't escalate by minting a token that claims role=admin: the server checks the DB."""
    forged = jwt.encode({"sub": "operator", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        Settings(_env_file=None).jwt_secret_key, algorithm="HS256")
    resp = await client.post("/api/simulator/reset", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 403


# ── simulator control: RBAC ──

@pytest.mark.parametrize("role,status", [("operator", 403), ("engineer", 200), ("admin", 200)])
async def test_inject_fault_rbac(client, auth, bus, role, status):
    resp = await client.post("/api/simulator/fault/bearing_wear", headers=auth[role])
    assert resp.status_code == status
    commands = await bus.get_recent_events("simulator.command")
    if status == 200:
        assert resp.json() == {"status": "ok", "scenario": "bearing_wear"}
        assert [c["data"] for c in commands] == [{"action": "inject_fault", "scenario": "bearing_wear"}]
        assert commands[0]["agent"] == "api"
    else:
        assert resp.json()["detail"] == "Insufficient permissions"
        assert commands == []


@pytest.mark.parametrize("role,status", [("operator", 403), ("engineer", 200), ("admin", 200)])
async def test_reset_rbac(client, auth, bus, role, status):
    resp = await client.post("/api/simulator/reset", headers=auth[role])
    assert resp.status_code == status
    commands = await bus.get_recent_events("simulator.command")
    assert [c["data"] for c in commands] == ([{"action": "reset"}] if status == 200 else [])


@pytest.mark.parametrize("scenario", [s.value for s in FaultScenario])
async def test_every_valid_scenario_is_accepted(client, auth, scenario):
    assert (await client.post(f"/api/simulator/fault/{scenario}", headers=auth["engineer"])).status_code == 200


async def test_invalid_scenario_is_400_and_publishes_nothing(client, auth, bus):
    resp = await client.post("/api/simulator/fault/meteor_strike", headers=auth["admin"])
    assert resp.status_code == 400
    assert "bearing_wear" in resp.json()["detail"]
    assert await bus.get_recent_events("simulator.command") == []


# ── telemetry history ──

async def test_history_is_empty_before_any_telemetry(client, auth):
    assert (await client.get("/api/telemetry/history", headers=auth["operator"])).json() == []
    assert (await client.get("/api/telemetry/asset-history", headers=auth["operator"])).json() == []


async def test_history_returns_stored_telemetry_oldest_first(client, auth, run_ticks):
    await run_ticks(12)
    rows = (await client.get("/api/telemetry/history", headers=auth["operator"])).json()
    assert len(rows) == 12
    stamps = [r["timestamp"] for r in rows]
    assert stamps == sorted(stamps)
    assert set(rows[0]) == {"timestamp", "engine_id", "egt", "rpm_n1", "rpm_n2", "vibration", "fuel_flow",
                            "oil_pressure", "oil_temp", "anomaly_score", "is_anomaly"}
    assert all(r["engine_id"] == "engine-001" and r["is_anomaly"] is False for r in rows)


async def test_history_limit_returns_the_most_recent_rows(client, auth, run_ticks):
    await run_ticks(12)
    everything = (await client.get("/api/telemetry/history", headers=auth["operator"])).json()
    last5 = (await client.get("/api/telemetry/history?limit=5", headers=auth["operator"])).json()
    assert last5 == everything[-5:]


async def test_asset_history_records_detected_faults(client, auth, run_ticks):
    await run_ticks(10)
    await run_ticks(25, fault=FaultScenario.BEARING_WEAR)
    rows = (await client.get("/api/telemetry/asset-history", headers=auth["engineer"])).json()
    assert rows and all(r["event_type"] == "fault_detected" and r["fault_type"] == "bearing_wear" for r in rows)
    assert set(rows[0]) == {"timestamp", "engine_id", "event_type", "fault_type", "description", "resolved"}
    assert all(r["resolved"] is False for r in rows)
    history = (await client.get("/api/telemetry/history?limit=500", headers=auth["engineer"])).json()
    assert any(r["is_anomaly"] for r in history)
