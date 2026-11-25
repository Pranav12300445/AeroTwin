# 🛩️ AeroTwin — UAV Engine Digital-Twin Health Monitoring Agent

> **SIH 2026 — SIH26054**
>
> An agentic digital-twin assistant that monitors UAV-engine health, predicts faults, and coordinates maintenance recommendations using a multi-agent system with RAG and LLM reasoning.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Pranav12300445/AeroTwin.git && cd AeroTwin

# 2. Create .env from template
cp .env.example .env
# Edit .env → add your GROQ_API_KEY (get one free at https://console.groq.com/keys)

# 3. Launch everything
docker compose up --build
```

Then open:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/api/health

## Default Credentials

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Operator | `operator` | `operator123` | View telemetry, alerts (read-only) |
| Engineer | `engineer` | `engineer123` | + Full maintenance details, fault injection |
| Admin | `admin` | `admin123` | + System config, simulator reset |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    AeroTwin Architecture                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Engine Simulator ──► Telemetry Monitor Agent                │
│       (6 channels)       │                                   │
│                          ▼                                   │
│                    Digital Twin Sync Agent                    │
│                    (Brayton-cycle physics)                    │
│                          │                                   │
│                          ▼                                   │
│                    Fault Predictor Agent ──► RUL Estimation   │
│                    (Z-score anomaly)                          │
│                          │                                   │
│                          ▼                                   │
│                    Maintenance Planner Agent                  │
│                    (RAG + LLM reasoning)                     │
│                          │                                   │
│          ┌───────────────┼───────────────┐                   │
│          ▼               ▼               ▼                   │
│     TimescaleDB     ChromaDB         Dashboard               │
│     (telemetry)     (procedures)     (Next.js)               │
│                                                              │
│  ◄──────── Redis Pub/Sub + Streams (event bus) ────────────► │
└──────────────────────────────────────────────────────────────┘
```

**4 Agents** (event-driven coordination via Redis):
1. **Telemetry Monitor** — ingests 6 sensor channels, detects anomalies (z-score)
2. **Digital Twin Sync** — Brayton-cycle physics model, computes residuals, tracks health factor
3. **Fault Predictor** — classifies faults from anomaly features, predicts Remaining Useful Life
4. **Maintenance Planner** — retrieves procedures via RAG (ChromaDB) + generates recommendations via LLM (Groq, model set by `GROQ_MODEL`)

## Sensor Channels

| Channel | Normal Range | Fault Indicator |
|---------|-------------|-----------------|
| EGT (°C) | 580–680 | Bearing wear ↑, Compressor stall ↑↑ |
| RPM N1/N2 | 68k–82k | Compressor stall ↑↓, Fuel clog ↓ |
| Vibration (g) | 0.3–1.2 | Bearing wear ↑↑ |
| Fuel Flow (L/min) | 0.35–0.55 | Fuel nozzle clog ↓↓ |
| Oil Pressure (PSI) | 45–65 | Bearing wear ↓ |
| Oil Temp (°C) | 70–95 | Bearing wear ↑ |

## Demo Scenarios

Use the dashboard buttons (login as `engineer` or `admin`) or API:

| Scenario | Duration | Key Symptoms |
|----------|----------|-------------|
| 🔴 Bearing Wear | 60s gradual | Vibration ↑ 8g, oil temp ↑ 40°C, oil pressure ↓ |
| 🟠 Compressor Stall | 5s sudden | RPM spike then collapse, EGT surge, violent vibration |
| 🟡 Fuel Nozzle Clog | 30s gradual | Fuel flow ↓, erratic EGT, slow RPM decay |
| ✅ Reset Normal | Instant | All parameters return to baseline |

## Key Features

- **Real-time WebSocket streaming** — 1Hz telemetry with live gauge bars and line charts
- **AI-enhanced maintenance** — LLM generates structured recommendations with safety notes
- **RAG retrieval** — 5 synthetic maintenance manuals indexed in ChromaDB
- **Physics-informed digital twin** — Brayton-cycle model with health factor degradation
- **Role-based access control** — JWT auth with 3 roles (operator/engineer/admin)
- **Alert notifications** — Toast notifications for anomaly and fault transitions
- **Engine schematic SVG** — Cross-section with fault zone highlighting
- **Observability** — Agent activity log with per-agent color coding

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13 + FastAPI + Uvicorn |
| Frontend | Next.js 15 + React 19 + Tailwind CSS |
| Database | TimescaleDB (PostgreSQL 16 hypertable) |
| Messaging | Redis 7 Pub/Sub + Streams |
| RAG | ChromaDB + all-MiniLM-L6-v2 |
| LLM | Groq free tier (`GROQ_MODEL`, default `openai/gpt-oss-120b`; 30 req/min) |
| Anomaly Detection | z-score vs. a fixed calibrated baseline (7 features) + rule-based fault classifier |
| RUL Prediction | Degradation model with fault-specific base hours |
| Auth | JWT + bcrypt + RBAC (3 roles) |
| Deploy | Docker Compose (4 services) |

## Project Structure

```
AeroTwin/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + telemetry pipeline
│   │   ├── config.py            # Pydantic settings from .env
│   │   ├── event_bus.py         # Redis pub/sub + streams
│   │   ├── api/routes.py        # REST + WebSocket endpoints
│   │   ├── agents/
│   │   │   ├── coordinator.py   # Maintenance Planner (RAG + LLM)
│   │   │   └── llm_client.py    # Groq API client
│   │   ├── simulator/engine.py  # 6-channel fault-injectable telemetry
│   │   ├── twin/digital_twin.py # Brayton-cycle physics model
│   │   ├── ml/anomaly.py        # Z-score anomaly + RUL predictor
│   │   ├── rag/retriever.py     # ChromaDB RAG pipeline
│   │   ├── auth/auth.py         # JWT + RBAC
│   │   ├── db/database.py       # TimescaleDB ORM
│   │   └── models/schemas.py    # Pydantic models
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Login page
│   │   │   └── dashboard/page.tsx  # Main dashboard
│   │   ├── components/
│   │   │   ├── TelemetryCharts.tsx     # Gauges + line charts
│   │   │   ├── FaultTimeline.tsx       # Status + RUL + fault history
│   │   │   ├── MaintenancePanel.tsx    # LLM-enhanced procedures
│   │   │   ├── EngineSchematic.tsx     # SVG cross-section
│   │   │   ├── AgentActivityLog.tsx    # Agent event trace
│   │   │   ├── FaultInjectionButtons.tsx # Demo scenario controls
│   │   │   └── AlertToast.tsx          # Notification toasts
│   │   ├── hooks/useWebSocket.ts       # WebSocket with auto-reconnect
│   │   └── lib/api.ts                  # API client
│   ├── package.json
│   └── Dockerfile
├── maintenance_docs/            # 5 synthetic maintenance manuals
├── docs/                        # Design decisions & prerequisites
├── docker-compose.yml           # 4 services: api, timescaledb, redis, frontend
├── .env.example
└── README.md
```

## Development (without Docker)

```bash
# Backend
cd backend
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# Redis & Postgres must be running locally
```

## License

Built for Smart India Hackathon 2026.

## Testing

No Docker needed: the suites swap TimescaleDB for SQLite and Redis for an in-process fake.

```bash
# Backend: unit + integration (329 tests)
cd backend
pip install -r requirements-dev.txt
pytest                         # everything
pytest -m integration          # API + DB + event bus + agents + real WebSocket handshakes
pytest --cov=app               # coverage (.coveragerc included)

# Frontend (102 tests)
cd frontend
npm install
npm test
```

Notes: the RAG tests use real ChromaDB with an offline embedder and are skipped automatically
if `chromadb` isn't installed. WebSocket connections now require a JWT (`/ws/telemetry?token=...`);
only engineers/admins can send fault commands over it.
