# AeroTwin — Design Decisions (Updated)
## Changelog

### v1.1 — Ponytail Review Applied (Nov 22, 2026)

**13 findings resolved, net −85 lines cut:**

| Change | File | Detail |
|--------|------|--------|
| Deleted 5 unused Pydantic models | `schemas.py` | `TelemetryWithAnalysis`, `FaultPrediction`, `MaintenanceRecommendation`, `AgentEvent`, `UserCreate` — never imported anywhere |
| Deleted `SHUTDOWN` enum value | `schemas.py` | Never produced or consumed |
| Deleted `FaultType` enum | `schemas.py` | Codebase uses raw strings — enum was aspirational |
| Removed dead imports | `routes.py`, `database.py`, `main.py`, `digital_twin.py` | `json`, `math`, `Optional`, `SAEnum`, unused schema imports |
| Removed `get_ws_connections()` | `routes.py` | Never called |
| Removed pool tuning | `database.py` | `pool_size=10, max_overflow=20` unnecessary for single-user hackathon |
| Fixed misleading docstring | `anomaly.py` | Said "LSTM Autoencoder" but it's a z-score detector |

### New Files Added
| File | Purpose |
|------|---------|
| `agents/coordinator.py` | Maintenance Planner agent — RAG retrieval on `fault.predicted` events |
| `Dockerfile` (backend) | Python 3.13 container |
| `docker-compose.yml` | Full stack: API + TimescaleDB + Redis + Frontend |
| `frontend/Dockerfile` | Next.js container |
| `frontend/package.json` | Dashboard dependencies |
| `README.md` | Quick start, architecture, demo scenarios |
