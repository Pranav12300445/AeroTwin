# 🛩️ AeroTwin — UAV Engine Digital-Twin Health Monitoring Agent

> **SIH 2026 — SIH26054**
>
> An agentic digital-twin assistant that monitors UAV-engine health, predicts faults, and coordinates maintenance recommendations.

## Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd AeroTwin

# 2. Create .env from template
cp .env.example .env
# Edit .env → add your GROQ_API_KEY

# 3. Launch everything
docker compose up --build
```

Then open:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/api/health

## Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Operator | `operator` | `operator123` |
| Engineer | `engineer` | `engineer123` |
| Admin | `admin` | `admin123` |

## Architecture

```
Engine Simulator → FastAPI → Redis Pub/Sub → 4 Agents → Dashboard
                      ↕              ↕
                 TimescaleDB     ChromaDB (RAG)
```

**4 Agents** (event-driven coordination via Redis):
1. **Telemetry Monitor** — ingests sensors, detects anomalies (z-score)
2. **Digital Twin Sync** — physics model (Brayton-cycle), computes residuals
3. **Fault Predictor** — classifies faults, predicts Remaining Useful Life
4. **Maintenance Planner** — RAG retrieval of maintenance procedures

## Demo Scenarios

Trigger from the dashboard or via API:

```bash
# Gradual bearing wear (60s progression)
curl -X POST http://localhost:8000/api/simulator/fault/bearing_wear -H "Authorization: Bearer <token>"

# Sudden compressor stall (5s)
curl -X POST http://localhost:8000/api/simulator/fault/compressor_stall -H "Authorization: Bearer <token>"

# Fuel nozzle clogging (30s)
curl -X POST http://localhost:8000/api/simulator/fault/fuel_nozzle_clog -H "Authorization: Bearer <token>"

# Reset to normal
curl -X POST http://localhost:8000/api/simulator/reset -H "Authorization: Bearer <token>"
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13 + FastAPI |
| Frontend | Next.js + React + Tailwind |
| Database | TimescaleDB (PostgreSQL) |
| Messaging | Redis Pub/Sub + Streams |
| RAG | ChromaDB + all-MiniLM-L6-v2 |
| LLM | Groq (Llama 3.1 70B) |
| ML | Z-score anomaly detection + RUL predictor |
| Deploy | Docker Compose |

## Project Structure

```
AeroTwin/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + telemetry pipeline
│   │   ├── config.py         # Settings from .env
│   │   ├── event_bus.py       # Redis pub/sub + streams
│   │   ├── api/routes.py      # REST + WebSocket endpoints
│   │   ├── agents/coordinator.py  # Agent event wiring + RAG
│   │   ├── simulator/engine.py    # Fault-injectable telemetry
│   │   ├── twin/digital_twin.py   # Physics-informed model
│   │   ├── ml/anomaly.py         # Anomaly detection + RUL
│   │   ├── rag/retriever.py      # ChromaDB RAG pipeline
│   │   ├── auth/auth.py          # JWT + RBAC
│   │   └── db/database.py        # TimescaleDB ORM
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # Next.js dashboard
├── maintenance_docs/        # Synthetic maintenance manuals (RAG source)
├── docs/                    # Design decisions & prerequisites
├── docker-compose.yml
├── .env.example
└── README.md
```

## License

Built for Smart India Hackathon 2026.
