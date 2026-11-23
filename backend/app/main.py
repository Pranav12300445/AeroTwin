"""
AeroTwin — Main FastAPI Application.

Ties together: Simulator → EventBus → Agents → Dashboard WebSocket.
"""

import asyncio
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db.database import init_db, get_session_factory
from .event_bus import get_event_bus
from .simulator.engine import EngineSimulator, FaultScenario
from .twin.digital_twin import DigitalTwin
from .ml.anomaly import AnomalyDetector, RULPredictor
from .api.routes import auth_router, telemetry_router, simulator_router, ws_router, broadcast_to_clients
from .auth.auth import seed_default_users
from .agents.coordinator import setup_agent_subscriptions
from .db.database import TelemetryRecord, AssetHistory

logger = structlog.get_logger()

# ── Global instances ──
simulator = EngineSimulator()
digital_twin = DigitalTwin()
anomaly_detector = AnomalyDetector()
rul_predictor = RULPredictor()


async def process_telemetry(reading):
    """
    Main pipeline: Telemetry → Twin → Anomaly Detection → Fault Prediction.

    This is called every time the simulator emits a reading.
    """
    bus = get_event_bus()
    reading_dict = reading.model_dump()

    # 1. Digital Twin — compute expected vs actual
    twin_result = digital_twin.compute_residual(reading)

    # 2. Anomaly Detection
    anomaly_result = anomaly_detector.score(reading_dict)

    # 3. RUL Prediction (if anomaly detected)
    fault_type = "none"
    if anomaly_result["is_anomaly"]:
        # Map top anomaly feature to likely fault type
        feature = anomaly_result["top_anomaly_feature"]
        fault_map = {
            "vibration": "bearing_wear",
            "oil_pressure": "bearing_wear",
            "oil_temp": "bearing_wear",
            "rpm_n1": "compressor_stall",
            "rpm_n2": "compressor_stall",
            "fuel_flow": "fuel_nozzle_clog",
            "egt": "turbine_erosion",
        }
        fault_type = fault_map.get(feature, "none")

    rul = rul_predictor.predict(anomaly_result["anomaly_score"], fault_type)

    # 4. Determine engine status
    score = anomaly_result["anomaly_score"]
    if score > 0.7:
        status = "critical"
    elif score > 0.4:
        status = "warning"
    else:
        status = "normal"

    # 5. Build combined payload for dashboard
    dashboard_payload = {
        **reading_dict,
        "timestamp": reading_dict["timestamp"].isoformat() if hasattr(reading_dict["timestamp"], "isoformat") else str(reading_dict["timestamp"]),
        "twin_expected_egt": twin_result["expected_egt"],
        "twin_residual": twin_result["residual"],
        "twin_health_factor": twin_result["health_factor"],
        "twin_drift_detected": twin_result["drift_detected"],
        "anomaly_score": anomaly_result["anomaly_score"],
        "is_anomaly": anomaly_result["is_anomaly"],
        "top_anomaly_feature": anomaly_result["top_anomaly_feature"],
        "fault_type": fault_type,
        "rul_hours": rul,
        "engine_status": status,
    }

    # 6. Broadcast to WebSocket clients
    await broadcast_to_clients("telemetry", dashboard_payload)

    # 7. Publish events to Redis for agents
    await bus.publish("telemetry.raw", dashboard_payload, agent_name="telemetry_monitor")

    if anomaly_result["is_anomaly"]:
        await bus.publish("anomaly.detected", {
            "message": f"Anomaly detected! Score: {score:.3f}, Feature: {anomaly_result['top_anomaly_feature']}",
            "anomaly_score": score,
            "fault_type": fault_type,
            "rul_hours": rul,
            "top_feature": anomaly_result["top_anomaly_feature"],
            "feature_scores": anomaly_result["feature_scores"],
        }, agent_name="telemetry_monitor")

    if twin_result["drift_detected"]:
        await bus.publish("twin.residual", {
            "message": f"Twin drift detected! Residual: {twin_result['residual']:.1f}°C, Health: {twin_result['health_factor']:.3f}",
            **twin_result,
        }, agent_name="digital_twin_sync")

    if fault_type != "none" and anomaly_result["is_anomaly"]:
        await bus.publish("fault.predicted", {
            "message": f"Fault predicted: {fault_type} (confidence: {score:.1%}), RUL: {rul} hours",
            "fault_type": fault_type,
            "confidence": score,
            "rul_hours": rul,
            "severity": status,
        }, agent_name="fault_predictor")

    # 8. Store in DB (async, non-blocking)
    try:
        factory = get_session_factory()
        async with factory() as session:
            record = TelemetryRecord(
                timestamp=reading.timestamp,
                engine_id=reading.engine_id,
                egt=reading.egt,
                rpm_n1=reading.rpm_n1,
                rpm_n2=reading.rpm_n2,
                vibration=reading.vibration,
                fuel_flow=reading.fuel_flow,
                oil_pressure=reading.oil_pressure,
                oil_temp=reading.oil_temp,
                oat=reading.oat,
                altitude=reading.altitude,
                anomaly_score=anomaly_result["anomaly_score"],
                is_anomaly=anomaly_result["is_anomaly"],
                fault_type=fault_type if fault_type != "none" else None,
            )
            session.add(record)

            # Log asset history for significant events
            if anomaly_result["is_anomaly"] and fault_type != "none":
                history = AssetHistory(
                    engine_id=reading.engine_id,
                    event_type="fault_detected",
                    fault_type=fault_type,
                    description=f"Anomaly score: {score:.3f}, RUL: {rul} hours" if rul else f"Anomaly score: {score:.3f}",
                )
                session.add(history)

            await session.commit()
    except Exception as e:
        logger.warning("db_write_failed", error=str(e))


async def handle_simulator_command(event: dict):
    """Handle simulator control commands from API/dashboard."""
    data = event.get("data", {})
    action = data.get("action")

    if action == "inject_fault":
        scenario = data.get("scenario", "none")
        try:
            fault = FaultScenario(scenario)
            simulator.inject_fault(fault)
            logger.info("fault_injected", scenario=scenario)
        except ValueError:
            logger.warning("invalid_fault_scenario", scenario=scenario)

    elif action == "reset":
        simulator.inject_fault(FaultScenario.NONE)
        digital_twin.reset()
        logger.info("simulator_reset")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()

    # 1. Init database
    logger.info("initializing_database")
    await init_db()

    # 2. Seed default users
    factory = get_session_factory()
    async with factory() as session:
        await seed_default_users(session)

    # 3. Connect event bus
    bus = get_event_bus()
    await bus.connect()
    logger.info("event_bus_connected")

    # 4. Subscribe to simulator commands
    await bus.subscribe("simulator.command", handle_simulator_command)

    # 5. Wire up agent subscriptions (Maintenance Planner listens for faults)
    await setup_agent_subscriptions()

    # 6. Subscribe to maintenance + agent activity for WebSocket forwarding
    async def forward_maintenance(event: dict):
        await broadcast_to_clients("maintenance", event.get("data", {}))

    async def forward_agent_activity(event: dict):
        await broadcast_to_clients("agent_activity", event.get("data", event))

    await bus.subscribe("maintenance.recommended", forward_maintenance)
    await bus.subscribe("agent.activity", forward_agent_activity)

    # 7. Start event bus listener
    listener_task = asyncio.create_task(bus.listen())

    # 8. Start simulator
    simulator_task = None
    if settings.simulator_enabled:
        simulator.interval_ms = settings.simulator_interval_ms
        simulator_task = asyncio.create_task(simulator.run(process_telemetry))
        logger.info("simulator_started", interval_ms=settings.simulator_interval_ms)

    logger.info("aerotwin_started", env=settings.app_env)

    yield

    # Shutdown
    simulator.stop()
    bus.stop()
    if simulator_task:
        simulator_task.cancel()
    listener_task.cancel()
    await bus.disconnect()
    logger.info("aerotwin_shutdown")


# ── Create FastAPI app ──
app = FastAPI(
    title="AeroTwin",
    description="UAV Engine Digital-Twin Health Monitoring Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(telemetry_router)
app.include_router(simulator_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {
        "app": "AeroTwin",
        "version": "1.0.0",
        "description": "UAV Engine Digital-Twin Health Monitoring Agent",
        "status": "running",
        "active_fault": simulator.active_fault.value,
    }


@app.get("/api/health")
async def health():
    return {"status": "healthy"}

