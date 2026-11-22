# Routine Engine Health Check Procedure
## Document: MX-PROC-004 | UAV Turbine Engine Scheduled Maintenance

### 1. Purpose
Standard routine health check for UAV turbine engines. Performed at regular intervals
to establish baseline performance and detect early signs of degradation.

### 2. Schedule
- **Pre-flight**: Abbreviated check before every flight
- **25-hour**: Basic parameter check
- **100-hour**: Comprehensive inspection
- **500-hour**: Major inspection with component removal

### 3. Pre-Flight Check (5 minutes)
1. Visual inspection — inlet clear, exhaust clear, no leaks
2. Oil level check — must be between MIN and MAX marks
3. Fuel system — no leaks, filter indicator green
4. Ground run to idle — listen for unusual sounds
5. Check telemetry readings at idle:
   - EGT: 280-350°C
   - RPM N1: 32,000-38,000
   - Vibration: <1.0g
   - Oil Pressure: >40 PSI
6. If all normal — CLEARED FOR FLIGHT

### 4. 25-Hour Parameter Check (30 minutes)
1. Ground run through full power range
2. Record at IDLE, 50%, 75%, 100%:
   - EGT, RPM N1, RPM N2, Vibration, Fuel Flow, Oil Pressure, Oil Temp
3. Compare with baseline (first-run data)
4. Flag any parameter >10% deviation from baseline
5. Download digital twin health report
6. Update maintenance log

### 5. 100-Hour Comprehensive Inspection (4-6 hours)
1. All 25-hour checks PLUS:
2. Oil sample analysis — send to lab for metal content
3. Fuel filter replacement
4. Inlet screen cleaning
5. Borescope inspection of compressor and turbine
6. Bearing vibration spectrum analysis
7. Fuel nozzle flow check
8. Control system calibration verification
9. Exhaust inspection for hot spots or discoloration

### 6. Parameter Limits

| Parameter | Normal Range | Warning | Critical |
|-----------|-------------|---------|----------|
| EGT (cruise) | 580-680°C | >700°C | >800°C |
| RPM N1 | 68,000-78,000 | <65,000 or >80,000 | <60,000 or >85,000 |
| RPM N2 | 72,000-82,000 | <69,000 or >84,000 | <65,000 or >88,000 |
| Vibration | 0.3-1.2g | >2.0g | >4.0g |
| Fuel Flow | 0.35-0.55 L/min | <0.25 or >0.65 | <0.15 or >0.80 |
| Oil Pressure | 45-65 PSI | <40 PSI | <30 PSI |
| Oil Temp | 70-95°C | >105°C | >120°C |

### 7. Digital Twin Integration
- Compare actual readings against digital twin predictions
- Residual >15°C on EGT — schedule detailed inspection
- Health factor <0.90 — increase monitoring frequency
- Health factor <0.80 — schedule maintenance action
- Any drift detection alert — investigate within 5 flight hours

