"""
API Routes — Telemetry, Auth, Simulator Control, and Dashboard endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db, User, TelemetryRecord, AssetHistory
from ..auth.auth import (
    verify_password, create_access_token, decode_access_token,
    get_current_user, require_role,
)
from ..models.schemas import UserResponse, TokenResponse, UserRole
from ..event_bus import get_event_bus

import json


# ──────────────────────────────────────────────
# Auth Router
# ──────────────────────────────────────────────

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.username, user.role)
    return TokenResponse(access_token=token, role=UserRole(user.role))


@auth_router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(username=user.username, role=UserRole(user.role))


# ──────────────────────────────────────────────
# Telemetry Router
# ──────────────────────────────────────────────

telemetry_router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@telemetry_router.get("/history")
async def get_telemetry_history(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get recent telemetry records."""
    result = await db.execute(
        select(TelemetryRecord).order_by(desc(TelemetryRecord.timestamp)).limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "engine_id": r.engine_id,
            "egt": r.egt,
            "rpm_n1": r.rpm_n1,
            "rpm_n2": r.rpm_n2,
            "vibration": r.vibration,
            "fuel_flow": r.fuel_flow,
            "oil_pressure": r.oil_pressure,
            "oil_temp": r.oil_temp,
            "anomaly_score": r.anomaly_score,
            "is_anomaly": r.is_anomaly,
        }
        for r in reversed(records)
    ]


@telemetry_router.get("/asset-history")
async def get_asset_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get asset maintenance history."""
    result = await db.execute(
        select(AssetHistory).order_by(desc(AssetHistory.timestamp)).limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "engine_id": r.engine_id,
            "event_type": r.event_type,
            "fault_type": r.fault_type,
            "description": r.description,
            "resolved": r.resolved,
        }
        for r in reversed(records)
    ]


# ──────────────────────────────────────────────
# Simulator Control Router
# ──────────────────────────────────────────────

simulator_router = APIRouter(prefix="/api/simulator", tags=["simulator"])


@simulator_router.post("/fault/{scenario}")
async def inject_fault(
    scenario: str,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.MAINTENANCE_ENGINEER)),
):
    """Inject a fault scenario into the simulator."""
    from ..simulator.engine import FaultScenario

    valid = [f.value for f in FaultScenario]
    if scenario not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Valid: {valid}")

    bus = get_event_bus()
    await bus.publish("simulator.command", {"action": "inject_fault", "scenario": scenario}, agent_name="api")
    return {"status": "ok", "scenario": scenario}


@simulator_router.post("/reset")
async def reset_simulator(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.MAINTENANCE_ENGINEER)),
):
    """Reset simulator to normal operation."""
    bus = get_event_bus()
    await bus.publish("simulator.command", {"action": "reset"}, agent_name="api")
    return {"status": "ok", "action": "reset"}


# ──────────────────────────────────────────────
# WebSocket — Real-time Telemetry Stream
# ──────────────────────────────────────────────

ws_router = APIRouter()

_ws_connections: set[WebSocket] = set()


# Roles allowed to send commands over the socket (same as the REST fault endpoints)
_WS_COMMAND_ROLES = {UserRole.ADMIN.value, UserRole.MAINTENANCE_ENGINEER.value}


@ws_router.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket, token: str = ""):
    """WebSocket endpoint for real-time telemetry + agent events.

    Requires a valid JWT as ?token=... — an invalid token is rejected (policy violation, 1008).
    """
    claims = decode_access_token(token)
    if claims is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    role = claims.get("role")

    await websocket.accept()
    _ws_connections.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "inject_fault" and role in _WS_COMMAND_ROLES:
                    bus = get_event_bus()
                    await bus.publish(
                        "simulator.command",
                        {"action": "inject_fault", "scenario": cmd.get("scenario", "none")},
                        agent_name="dashboard",
                    )
            except (json.JSONDecodeError, AttributeError):
                pass  # ignore malformed commands
    except WebSocketDisconnect:
        pass
    finally:
        _ws_connections.discard(websocket)


async def broadcast_to_clients(event_type: str, data: dict):
    """Broadcast data to all connected WebSocket clients."""
    if not _ws_connections:
        return
    message = json.dumps({"type": event_type, "data": data}, default=str)
    dead = set()
    for ws in list(_ws_connections):  # copy: handlers may add/discard while we await
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _ws_connections.difference_update(dead)  # in-place: `-=` would rebind the global and raise UnboundLocalError
