"""
Database layer — TimescaleDB schema and async connection.

Tables:
    telemetry       — hypertable for time-series sensor data
    asset_history   — maintenance events and status changes
    users           — RBAC user accounts
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Boolean, Text, text
from datetime import datetime, timezone

from ..config import get_settings


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────
# ORM Models
# ──────────────────────────────────────────────

class TelemetryRecord(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    engine_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    egt: Mapped[float] = mapped_column(Float, nullable=False)
    rpm_n1: Mapped[float] = mapped_column(Float, nullable=False)
    rpm_n2: Mapped[float] = mapped_column(Float, nullable=False)
    vibration: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_flow: Mapped[float] = mapped_column(Float, nullable=False)
    oil_pressure: Mapped[float] = mapped_column(Float, nullable=False)
    oil_temp: Mapped[float] = mapped_column(Float, nullable=False)
    oat: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Analysis results
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    fault_type: Mapped[str] = mapped_column(String(50), nullable=True)


class AssetHistory(Base):
    __tablename__ = "asset_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    engine_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # fault_detected, maintenance_done, etc.
    fault_type: Mapped[str] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="operator")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ──────────────────────────────────────────────
# Engine & Session
# ──────────────────────────────────────────────

_engine = None
_session_factory = None


def get_async_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_async_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db():
    """Create all tables. Call once on startup."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create TimescaleDB hypertable for telemetry (if extension available)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            await conn.execute(text(
                "SELECT create_hypertable('telemetry', 'timestamp', "
                "if_not_exists => TRUE, migrate_data => TRUE);"
            ))
        except Exception:
            # TimescaleDB not available — plain PostgreSQL still works
            pass

