"""
UAV Turbine Engine Simulator.

Generates realistic telemetry for a small turbine/jet engine (JetCat P-series style)
with injectable fault scenarios.

Normal Operating Ranges (cruise):
    EGT:          580–680 °C
    RPM N1:       68,000–78,000
    RPM N2:       72,000–82,000
    Vibration:    0.3–1.2 g
    Fuel Flow:    0.35–0.55 L/min
    Oil Pressure: 45–65 PSI
    Oil Temp:     70–95 °C
"""

import asyncio
import math
import random
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from ..models.schemas import TelemetryReading, FaultType


class FaultScenario(str, Enum):
    NONE = "none"
    BEARING_WEAR = "bearing_wear"
    COMPRESSOR_STALL = "compressor_stall"
    FUEL_NOZZLE_CLOG = "fuel_nozzle_clog"


class EngineSimulator:
    """Simulates a small turbine engine with 6 sensor channels and fault injection."""

    # Normal cruise operating parameters
    NOMINAL = {
        "egt": 630.0,
        "rpm_n1": 73000.0,
        "rpm_n2": 77000.0,
        "vibration": 0.7,
        "fuel_flow": 0.45,
        "oil_pressure": 55.0,
        "oil_temp": 82.0,
        "oat": 25.0,
        "altitude": 500.0,
    }

    # Noise standard deviations (normal operation)
    NOISE = {
        "egt": 3.0,
        "rpm_n1": 200.0,
        "rpm_n2": 200.0,
        "vibration": 0.05,
        "fuel_flow": 0.01,
        "oil_pressure": 1.0,
        "oil_temp": 0.5,
    }

    def __init__(self, engine_id: str = "engine-001", interval_ms: int = 1000):
        self.engine_id = engine_id
        self.interval_ms = interval_ms

        # State
        self._active_fault: FaultScenario = FaultScenario.NONE
        self._fault_start_time: Optional[float] = None
        self._fault_progress: float = 0.0  # 0.0 to 1.0
        self._running: bool = False
        self._tick: int = 0

        # Flight cycle position (simulates throttle changes)
        self._flight_phase_offset = random.uniform(0, 2 * math.pi)

    def inject_fault(self, fault: FaultScenario) -> None:
        """Inject a fault scenario. Call with NONE to clear."""
        self._active_fault = fault
        self._fault_start_time = time.time() if fault != FaultScenario.NONE else None
        self._fault_progress = 0.0

    @property
    def active_fault(self) -> FaultScenario:
        return self._active_fault

    def _get_fault_progress(self) -> float:
        """Progress of fault from 0 (just started) to 1 (fully degraded)."""
        if self._fault_start_time is None:
            return 0.0

        elapsed = time.time() - self._fault_start_time

        if self._active_fault == FaultScenario.BEARING_WEAR:
            # Gradual: takes ~60 seconds to reach full severity
            self._fault_progress = min(1.0, elapsed / 60.0)
        elif self._active_fault == FaultScenario.COMPRESSOR_STALL:
            # Sudden: reaches full severity in ~5 seconds
            self._fault_progress = min(1.0, elapsed / 5.0)
        elif self._active_fault == FaultScenario.FUEL_NOZZLE_CLOG:
            # Moderate: takes ~30 seconds
            self._fault_progress = min(1.0, elapsed / 30.0)

        return self._fault_progress

    def _throttle_factor(self) -> float:
        """Simulate gentle throttle variations (0.85 to 1.15)."""
        t = self._tick * (self.interval_ms / 1000.0)
        return 1.0 + 0.1 * math.sin(0.1 * t + self._flight_phase_offset) + 0.05 * math.sin(0.23 * t)

    def generate_reading(self) -> TelemetryReading:
        """Generate one telemetry snapshot."""
        self._tick += 1
        throttle = self._throttle_factor()
        progress = self._get_fault_progress()
        nom = self.NOMINAL
        noise = self.NOISE

        # Base values = nominal × throttle + noise
        egt = nom["egt"] * throttle + random.gauss(0, noise["egt"])
        rpm_n1 = nom["rpm_n1"] * throttle + random.gauss(0, noise["rpm_n1"])
        rpm_n2 = nom["rpm_n2"] * throttle + random.gauss(0, noise["rpm_n2"])
        vibration = nom["vibration"] + random.gauss(0, noise["vibration"])
        fuel_flow = nom["fuel_flow"] * throttle + random.gauss(0, noise["fuel_flow"])
        oil_pressure = nom["oil_pressure"] + random.gauss(0, noise["oil_pressure"])
        oil_temp = nom["oil_temp"] + random.gauss(0, noise["oil_temp"])

        # ── Apply fault effects ──
        if self._active_fault == FaultScenario.BEARING_WEAR:
            # Gradual vibration increase + oil temp rise + oil pressure drop
            vibration += progress * 8.0  # 0.7 → up to 8.7g
            vibration += progress * random.gauss(0, 1.5)  # increasing noise
            oil_temp += progress * 40.0  # 82 → up to 122°C
            oil_pressure -= progress * 20.0  # 55 → down to 35 PSI
            egt += progress * 30.0  # slight EGT rise from friction

        elif self._active_fault == FaultScenario.COMPRESSOR_STALL:
            # Sudden RPM spike then drop, EGT surge, vibration spike
            if progress < 0.3:
                # Initial surge
                rpm_n1 += progress * 15000  # spike up
                rpm_n2 += progress * 12000
                egt += progress * 200  # EGT surge
                vibration += progress * 15  # violent vibration
            else:
                # Stall — RPM drops, EGT stays high
                rpm_n1 -= (progress - 0.3) * 30000  # RPM collapses
                rpm_n2 -= (progress - 0.3) * 25000
                egt += 150 - (progress - 0.3) * 50  # EGT slowly drops
                vibration += 5.0 + random.gauss(0, 2)  # still rough
                fuel_flow += progress * 0.3  # fuel pooling

        elif self._active_fault == FaultScenario.FUEL_NOZZLE_CLOG:
            # Fuel flow drops, EGT imbalance (erratic), RPM slowly drops
            fuel_flow -= progress * 0.25  # 0.45 → down to 0.20
            fuel_flow = max(0.05, fuel_flow)
            egt += progress * random.gauss(0, 40)  # erratic EGT
            egt -= progress * 20  # overall EGT drops (lean burn)
            rpm_n1 -= progress * 5000  # slow RPM decay
            rpm_n2 -= progress * 4000

        # Clamp to physical limits
        egt = max(0, min(1200, egt))
        rpm_n1 = max(0, min(120000, rpm_n1))
        rpm_n2 = max(0, min(120000, rpm_n2))
        vibration = max(0, min(50, vibration))
        fuel_flow = max(0, min(10, fuel_flow))
        oil_pressure = max(0, min(150, oil_pressure))
        oil_temp = max(0, min(200, oil_temp))

        return TelemetryReading(
            timestamp=datetime.now(timezone.utc),
            engine_id=self.engine_id,
            egt=round(egt, 2),
            rpm_n1=round(rpm_n1, 1),
            rpm_n2=round(rpm_n2, 1),
            vibration=round(vibration, 3),
            fuel_flow=round(fuel_flow, 4),
            oil_pressure=round(oil_pressure, 2),
            oil_temp=round(oil_temp, 2),
            oat=round(nom["oat"] + random.gauss(0, 0.3), 1),
            altitude=round(nom["altitude"] + random.gauss(0, 5), 1),
        )

    async def run(self, callback) -> None:
        """Run the simulator, calling callback(reading) every interval."""
        self._running = True
        while self._running:
            reading = self.generate_reading()
            await callback(reading)
            await asyncio.sleep(self.interval_ms / 1000.0)

    def stop(self) -> None:
        self._running = False

