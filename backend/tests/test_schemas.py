"""Tests for Pydantic schema models."""

from app.models.schemas import (
    TelemetryReading,
    UserResponse,
    TokenResponse,
    EngineStatus,
    UserRole,
)


def test_telemetry_reading_defaults():
    reading = TelemetryReading(
        egt=630.0,
        rpm_n1=73000.0,
        rpm_n2=77000.0,
        vibration=0.7,
        fuel_flow=0.45,
        oil_pressure=55.0,
        oil_temp=82.0,
    )
    assert reading.engine_id == "engine-001"
    assert reading.oat == 25.0
    assert reading.altitude == 0.0


def test_telemetry_reading_validation_rejects_out_of_range():
    from pydantic import ValidationError
    try:
        TelemetryReading(
            egt=2000.0,  # above max 1200
            rpm_n1=73000.0,
            rpm_n2=77000.0,
            vibration=0.7,
            fuel_flow=0.45,
            oil_pressure=55.0,
            oil_temp=82.0,
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_user_response_and_token_response():
    ur = UserResponse(username="engineer", role=UserRole.MAINTENANCE_ENGINEER)
    assert ur.username == "engineer"
    assert ur.role == UserRole.MAINTENANCE_ENGINEER

    tr = TokenResponse(access_token="abc123", role=UserRole.ADMIN)
    assert tr.access_token == "abc123"
    assert tr.token_type == "bearer"
    assert tr.role == UserRole.ADMIN


def test_engine_status_enum():
    assert EngineStatus.NORMAL == "normal"
    assert EngineStatus.WARNING == "warning"
    assert EngineStatus.CRITICAL == "critical"


def test_default_timestamp_is_timezone_aware_utc():
    from datetime import timezone
    from app.models.schemas import TelemetryReading
    r = TelemetryReading(egt=600, rpm_n1=70000, rpm_n2=75000, vibration=0.5, fuel_flow=0.4, oil_pressure=50, oil_temp=80)
    assert r.timestamp.tzinfo is not None and r.timestamp.utcoffset() == timezone.utc.utcoffset(None)


def test_telemetry_bounds_are_enforced():
    import pytest
    from pydantic import ValidationError
    from app.models.schemas import TelemetryReading
    ok = dict(egt=600, rpm_n1=70000, rpm_n2=75000, vibration=0.5, fuel_flow=0.4, oil_pressure=50, oil_temp=80)
    for field, bad in [("egt", 1201), ("egt", -1), ("vibration", 51), ("fuel_flow", 11), ("rpm_n1", 120001), ("oil_temp", 201)]:
        with pytest.raises(ValidationError):
            TelemetryReading(**{**ok, field: bad})
