"""
Shared fixtures.

Unit tests use the small component fixtures at the top. Integration tests use the infrastructure
fixtures below, which swap the external services for in-process stand-ins so the *real* FastAPI app,
event bus, agents and DB code run without Docker:

    TimescaleDB  ->  SQLite file (aiosqlite)     fixture: db
    Redis        ->  fakeredis (pub/sub+streams)  fixture: bus
    wall clock   ->  controllable fake clock      fixture: fake_clock
"""

import asyncio
import os
import random
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import pytest
import pytest_asyncio


# ──────────────────────────────────────────────
# Component fixtures (unit tests)
# ──────────────────────────────────────────────

@pytest.fixture
def anomaly_detector():
    from app.ml.anomaly import AnomalyDetector
    return AnomalyDetector()


@pytest.fixture
def rul_predictor():
    from app.ml.anomaly import RULPredictor
    return RULPredictor()


@pytest.fixture
def digital_twin():
    from app.twin.digital_twin import DigitalTwin
    return DigitalTwin()


@pytest.fixture
def simulator():
    from app.simulator.engine import EngineSimulator
    return EngineSimulator(interval_ms=100)


# ──────────────────────────────────────────────
# Isolation: reset module-level singletons around every test
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_global_state(monkeypatch):
    """The app keeps state in module globals; give each test fresh ones."""
    from app.agents import coordinator
    from app.api import routes
    from app import main
    from app.ml.anomaly import AnomalyDetector, RULPredictor
    from app.simulator.engine import EngineSimulator
    from app.twin.digital_twin import DigitalTwin

    routes._ws_connections.clear()
    coordinator._last_handled.clear()
    monkeypatch.setattr(coordinator, "_rag", None)
    monkeypatch.setattr(main, "simulator", EngineSimulator())
    monkeypatch.setattr(main, "digital_twin", DigitalTwin())
    monkeypatch.setattr(main, "anomaly_detector", AnomalyDetector())
    monkeypatch.setattr(main, "rul_predictor", RULPredictor())
    yield
    routes._ws_connections.clear()


# ──────────────────────────────────────────────
# Infrastructure stand-ins
# ──────────────────────────────────────────────

@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    """Empty SQLite database wired in as the app's DB. Yields the async session factory."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.db import database

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'aerotwin_test.db'}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(database, "_engine", engine)
    monkeypatch.setattr(database, "_session_factory", factory)
    async with engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def bus(monkeypatch):
    """A connected EventBus backed by fakeredis, installed as the app's singleton."""
    import fakeredis
    import fakeredis.aioredis

    from app import event_bus

    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        event_bus.aioredis, "from_url",
        lambda url, **kw: fakeredis.aioredis.FakeRedis(server=server, decode_responses=True),
    )
    b = event_bus.EventBus()
    await b.connect()
    monkeypatch.setattr(event_bus, "_event_bus", b)
    yield b
    b.stop()
    await b.disconnect()


@pytest_asyncio.fixture
async def listening_bus(bus):
    """The bus with its listener loop running (so subscribe() callbacks fire)."""
    task = asyncio.create_task(bus.listen())
    yield bus
    bus.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.fixture(scope="session")
def password_hashes():
    """bcrypt is deliberately slow; hash the demo passwords once per test session."""
    from app.auth.auth import hash_password
    return {
        "operator": hash_password("operator123"),
        "engineer": hash_password("engineer123"),
        "admin": hash_password("admin123"),
    }


@pytest_asyncio.fixture
async def seeded_db(db, password_hashes):
    """db + the three default users (same names/roles/passwords as seed_default_users)."""
    from app.db.database import User

    async with db() as s:
        s.add_all([
            User(username="operator", hashed_password=password_hashes["operator"], role="operator"),
            User(username="engineer", hashed_password=password_hashes["engineer"], role="maintenance_engineer"),
            User(username="admin", hashed_password=password_hashes["admin"], role="admin"),
        ])
        await s.commit()
    return db


@pytest_asyncio.fixture
async def client(seeded_db, bus):
    """httpx client talking to the real ASGI app (no lifespan: db and bus are already wired)."""
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def login_token(client, username: str) -> str:
    resp = await client.post("/api/auth/login", data={"username": username, "password": f"{username}123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def auth(client):
    """Authorization headers per role. Tokens are minted directly (bcrypt login is slow and is
    covered by its own tests); the server still validates them against the DB on every request."""
    from app.auth.auth import create_access_token

    roles = {"operator": "operator", "engineer": "maintenance_engineer", "admin": "admin"}
    return {name: {"Authorization": f"Bearer {create_access_token(name, role)}"} for name, role in roles.items()}


# ──────────────────────────────────────────────
# Time + sockets + agents
# ──────────────────────────────────────────────

@pytest.fixture
def fake_clock(monkeypatch):
    """Controllable replacement for the simulator's clock so 60 s fault ramps take no real time."""
    from app.simulator import engine

    clock = SimpleNamespace(now=1_000_000.0)
    clock.advance = lambda seconds=1.0: setattr(clock, "now", clock.now + seconds)
    monkeypatch.setattr(engine, "time", SimpleNamespace(time=lambda: clock.now))
    return clock


@pytest.fixture
def seeded_random():
    random.seed(1234)


class FakeWebSocket:
    """Minimal stand-in for starlette's WebSocket, driven from the test."""

    def __init__(self, incoming=()):
        self.incoming = list(incoming)
        self.sent: list[str] = []
        self.accepted = False
        self.close_code = None

    async def accept(self):
        self.accepted = True

    async def close(self, code: int = 1000):
        self.close_code = code

    async def receive_text(self):
        from fastapi import WebSocketDisconnect
        if not self.incoming:
            raise WebSocketDisconnect()
        return self.incoming.pop(0)

    async def send_text(self, message: str):
        self.sent.append(message)


@pytest.fixture
def fake_ws():
    return FakeWebSocket


class StubRAG:
    """Offline replacement for MaintenanceRAG."""

    def __init__(self, procedures=None):
        self.procedures = procedures if procedures is not None else [
            {"content": "Rotate shaft by hand and check for roughness.", "source": "bearing_inspection.md", "relevance_score": 0.91},
            {"content": "Measure radial play (max 0.05 mm).", "source": "bearing_inspection.md", "relevance_score": 0.84},
            {"content": "Idle test for five minutes.", "source": "routine_health_check.md", "relevance_score": 0.70},
        ]
        self.calls: list[str] = []

    def get_procedure_for_fault(self, fault_type):
        self.calls.append(fault_type)
        return self.procedures


@pytest.fixture
def stub_rag(monkeypatch):
    from app.agents import coordinator
    rag = StubRAG()
    monkeypatch.setattr(coordinator, "get_rag", lambda: rag)
    return rag


@pytest.fixture
def stub_llm(monkeypatch):
    """Replace the Groq call; set stub_llm.response to what the 'model' should return."""
    from app.agents import coordinator

    state = SimpleNamespace(response="", prompts=[])

    async def fake_ask(system_prompt, user_prompt):
        state.prompts.append((system_prompt, user_prompt))
        return state.response

    monkeypatch.setattr(coordinator, "ask_llm", fake_ask)
    return state


async def wait_for(predicate, timeout: float = 5.0, interval: float = 0.02):
    """Poll until predicate() is truthy (sync or async); fail the test on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return result
        await asyncio.sleep(interval)
    raise AssertionError("condition not met within %.1fs" % timeout)


# ──────────────────────────────────────────────
# Pipeline helpers (integration)
# ──────────────────────────────────────────────

@pytest.fixture
def ws_recorder():
    """A fake dashboard client registered with the real broadcast fan-out."""
    from app.api import routes

    sock = FakeWebSocket()
    routes._ws_connections.add(sock)

    def messages(kind=None):
        import json
        msgs = [json.loads(m) for m in sock.sent]
        return [m for m in msgs if kind is None or m["type"] == kind]

    sock.messages = messages
    return sock


@pytest.fixture
def run_ticks(db, bus, fake_clock, seeded_random, ws_recorder):
    """Drive the REAL pipeline (twin -> detector -> classifier -> bus -> DB -> WebSocket) n seconds
    at 1 Hz using the REAL simulator on a fake clock. Returns the telemetry payloads broadcast."""
    from app import main

    async def _run(n, fault=None):
        if fault is not None:
            main.simulator.inject_fault(fault)
        before = len(ws_recorder.messages("telemetry"))
        for _ in range(n):
            fake_clock.advance(1)
            await main.process_telemetry(main.simulator.generate_reading())
        return [m["data"] for m in ws_recorder.messages("telemetry")][before:]

    return _run
