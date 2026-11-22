# Compressor Stall Recovery & Inspection Procedure
## Document: MX-PROC-002 | UAV Turbine Engine Emergency Procedures

### 1. Purpose
Procedure for in-flight compressor stall recovery and subsequent ground inspection
of compressor section components.

### 2. Symptoms of Compressor Stall
- Sudden RPM spike followed by rapid decrease
- EGT surge exceeding 800°C
- Loud bang or popping sounds
- Severe vibration spike (>5g)
- Loss of thrust
- Fuel flow increase without corresponding thrust

### 3. In-Flight Emergency Recovery
**IMMEDIATE ACTIONS (memory items):**
1. THROTTLE — IDLE (immediately reduce to idle)
2. ALTITUDE — MAINTAIN (use remaining energy)
3. MONITOR EGT — if above 900°C, SHUT DOWN engine
4. WAIT 10 seconds at idle
5. THROTTLE — SLOWLY advance to 50%
6. If stall recurs — ENGINE SHUTDOWN and prepare for emergency landing

**DO NOT:**
- Rapidly cycle the throttle
- Attempt full-power restart without cool-down
- Continue mission — RTB (Return To Base) immediately

### 4. Post-Stall Ground Inspection

#### 4.1 External Inspection
1. Inspect inlet for FOD (Foreign Object Damage)
2. Check compressor blades visible through inlet — look for:
   - Bent or missing blades
   - Leading edge erosion
   - Tip rub marks on casing
3. Inspect exhaust nozzle for debris or discoloration

#### 4.2 Borescope Inspection
1. Insert borescope through inspection ports
2. Inspect each compressor stage:
   - Blade root attachments
   - Stator vane condition
   - Casing liner for rub marks
3. Document findings with photos

#### 4.3 Engine Data Review
1. Download flight data recorder
2. Review EGT, RPM, vibration traces during stall event
3. Compare with digital twin predictions
4. Determine if stall was:
   - Rotating stall (partial) — may be recoverable
   - Full surge — requires detailed inspection

### 5. Disposition
| Finding | Action |
|---------|--------|
| No blade damage, single stall event | Clear for flight with monitoring |
| Minor blade tip rub | Acceptable — monitor for 10 flight hours |
| Blade damage visible | ENGINE REMOVAL — shop overhaul required |
| Repeated stall events | ROOT CAUSE ANALYSIS required before return to service |

### 6. Estimated Downtime
- Post-stall inspection (no damage): 4-6 hours
- Borescope + data analysis: 8-12 hours
- Engine removal for overhaul: 3-5 days

