"""Pydantic models for telemetry, faults, and maintenance."""

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class EngineStatus(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class UserRole(str, Enum):
    OPERATOR = "operator"
    MAINTENANCE_ENGINEER = "maintenance_engineer"
    ADMIN = "admin"


# ──────────────────────────────────────────────
# Telemetry
# ──────────────────────────────────────────────

class TelemetryReading(BaseModel):
    """Single telemetry snapshot from all 6 sensor channels."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    engine_id: str = "engine-001"

    # Channel 1: Exhaust Gas Temperature (°C)
    egt: float = Field(..., description="Exhaust Gas Temperature in °C", ge=0, le=1200)

    # Channel 2: RPM — Spool speeds
    rpm_n1: float = Field(..., description="Low-pressure spool RPM", ge=0, le=120000)
    rpm_n2: float = Field(..., description="High-pressure spool RPM", ge=0, le=120000)

    # Channel 3: Vibration (g)
    vibration: float = Field(..., description="Vibration in g-force", ge=0, le=50)

    # Channel 4: Fuel flow (L/min)
    fuel_flow: float = Field(..., description="Fuel flow rate in L/min", ge=0, le=10)

    # Channel 5: Oil
    oil_pressure: float = Field(..., description="Oil pressure in PSI", ge=0, le=150)
    oil_temp: float = Field(..., description="Oil temperature in °C", ge=0, le=200)

    # Channel 6: Ambient
    oat: float = Field(default=25.0, description="Outside Air Temperature in °C")
    altitude: float = Field(default=0.0, description="Altitude in meters")


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

class UserResponse(BaseModel):
    username: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
