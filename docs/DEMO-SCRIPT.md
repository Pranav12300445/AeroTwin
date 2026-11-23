# AeroTwin Demo Script

## Setup
1. `docker compose up --build` (first time ~5 min)
2. Open http://localhost:3000

## Demo Flow (5 minutes)

### 1. Login as Admin (30s)
- Click **⚙️ Admin** quick login button
- Note: role badge, full dashboard with agent activity log

### 2. Normal Operation (30s)
- Watch live telemetry gauges (all green)
- Note: engine schematic shows all zones green
- Note: "No maintenance required" status
- Note: agent activity log shows telemetry_monitor events

### 3. Inject Bearing Wear (90s)
- Click **🔴 Bearing Wear** button
- Watch over 60 seconds:
  - Vibration gauge goes yellow → red
  - Oil temp rises, oil pressure drops
  - Engine schematic: shaft/bearing zones turn red
  - Toast notification: "⚠️ Anomaly detected!"
  - Toast notification: "🔴 Fault: Bearing Wear — RUL: Xh"
  - Fault prediction panel shows RUL countdown
  - Maintenance panel shows procedure (AI-Enhanced badge if Groq key set)
  - Agent activity log fills with events from all 4 agents

### 4. Reset & Switch Role (30s)
- Click **✅ Reset Normal** — watch everything return to green
- Logout → login as **👁️ Operator**
- Note: no fault injection buttons, simplified maintenance panel

### 5. Compressor Stall (30s)
- Logout → login as **🔧 Engineer**
- Click **🟠 Compressor Stall**
- Watch dramatic 5-second RPM spike then collapse
- Much faster detection → emergency maintenance recommendation

### 6. Architecture Walkthrough (60s)
- Open http://localhost:8000/docs — show API endpoints
- Explain: Simulator → Digital Twin → Anomaly Detector → Fault Predictor → Maintenance Planner
- Redis pub/sub coordinates agents, ChromaDB for RAG, TimescaleDB for time-series

## Key Talking Points
- **Multi-agent coordination**: 4 agents communicate via Redis event bus
- **Physics-informed**: Brayton-cycle digital twin, not just ML
- **RAG + LLM**: Real maintenance procedures + Groq Llama reasoning
- **Role-based access**: JWT RBAC with 3 roles
- **Observable**: Every agent action is logged and visible
- **Containerized**: One `docker compose up` to run everything
