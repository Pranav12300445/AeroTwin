"""ORM models, session dependency and init_db (SQLite stands in for TimescaleDB)."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import database
from app.db.database import AssetHistory, TelemetryRecord, User

NOW = datetime(2026, 11, 23, 9, 0, 0, tzinfo=timezone.utc)


def telemetry(**kw):
    base = dict(timestamp=NOW, engine_id="engine-001", egt=630.0, rpm_n1=73000.0, rpm_n2=77000.0,
                vibration=0.7, fuel_flow=0.45, oil_pressure=55.0, oil_temp=82.0, oat=25.0, altitude=500.0)
    base.update(kw)
    return TelemetryRecord(**base)


async def test_telemetry_record_roundtrip(db):
    async with db() as s:
        s.add(telemetry(anomaly_score=0.42, is_anomaly=True, fault_type="bearing_wear"))
        await s.commit()
    async with db() as s:
        r = (await s.execute(select(TelemetryRecord))).scalar_one()
    assert (r.engine_id, r.egt, r.rpm_n1, r.anomaly_score, r.is_anomaly, r.fault_type) == \
        ("engine-001", 630.0, 73000.0, 0.42, True, "bearing_wear")
    assert r.id is not None


async def test_telemetry_analysis_columns_are_optional(db):
    async with db() as s:
        s.add(telemetry())
        await s.commit()
        r = (await s.execute(select(TelemetryRecord))).scalar_one()
    assert r.anomaly_score is None and r.fault_type is None
    assert not r.is_anomaly  # default False


async def test_telemetry_requires_sensor_values(db):
    async with db() as s:
        s.add(TelemetryRecord(timestamp=NOW, engine_id="e"))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_asset_history_defaults(db):
    async with db() as s:
        s.add(AssetHistory(engine_id="engine-001", event_type="fault_detected"))
        await s.commit()
        h = (await s.execute(select(AssetHistory))).scalar_one()
    assert h.resolved is False
    assert h.timestamp is not None
    assert h.fault_type is None and h.description is None


async def test_user_defaults_and_unique_username(db):
    async with db() as s:
        s.add(User(username="alice", hashed_password="h"))
        await s.commit()
        u = (await s.execute(select(User))).scalar_one()
        assert u.role == "operator" and u.created_at is not None

        s.add(User(username="alice", hashed_password="h2"))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_get_db_yields_a_usable_session_and_closes_it(db):
    gen = database.get_db()
    session = await gen.__anext__()
    assert (await session.execute(select(User))).scalars().all() == []
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


async def test_engine_and_session_factory_are_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_session_factory", None)
    monkeypatch.setattr(database, "get_settings",
                        lambda: Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path/'x.db'}"))
    engine = database.get_async_engine()
    assert database.get_async_engine() is engine
    assert database.get_session_factory() is database.get_session_factory()
    await engine.dispose()


async def test_init_db_creates_tables_and_tolerates_missing_timescaledb(monkeypatch, tmp_path):
    """On plain SQLite the CREATE EXTENSION / create_hypertable statements fail; init_db must carry on."""
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_session_factory", None)
    monkeypatch.setattr(database, "get_settings",
                        lambda: Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path/'init.db'}"))
    await database.init_db()
    async with database.get_session_factory()() as s:
        s.add(User(username="u", hashed_password="h"))
        await s.commit()
        assert (await s.execute(select(User))).scalar_one().username == "u"
    await database.get_async_engine().dispose()


async def test_init_db_is_idempotent(db):
    await database.init_db()
    await database.init_db()
