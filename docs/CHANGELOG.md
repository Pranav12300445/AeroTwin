# AeroTwin — Design Decisions (Updated)
## Changelog

### v1.3 — Completion pass: bug fixes + full test suites (Nov 25, 2026)

**Bugs fixed** (each has a regression test):

| Area | Problem | Fix |
|------|---------|-----|
| `api/routes.py` | `_ws_connections -= dead` rebinds a global → `UnboundLocalError` on every broadcast; the simulator task died on its first tick | in-place `difference_update`; simulator loop also survives callback errors |
| `api/routes.py` | WebSocket had no auth; anyone could inject faults, bypassing RBAC | JWT required via `?token=`; only engineer/admin may send commands; frontend updated |
| `ml/anomaly.py` | Rolling baseline learned the fault: bearing wear "forgotten" after ~30 s, fuel clog never flagged; 11/300 false alarms | fixed baseline sized to the ±15 % throttle envelope: 0 false alarms, all faults sustained (40 seeds) |
| `main.py` | Fault type taken from the top z-score feature: compressor stall labelled `bearing_wear` ~92 % of the time | `classify_fault()` over the whole z-score signature |
| `twin/digital_twin.py` | Mis-calibrated (predicted ~685 °C vs 630 °C): health decayed and drift fired constantly in healthy operation | refitted coefficients, absolute drift floor |
| `agents/llm_client.py` | `llama-3.1-70b-versatile` (and later `llama-3.3-70b-versatile`) retired by Groq; errors swallowed so AI never worked | `GROQ_MODEL` setting, default `openai/gpt-oss-120b`, larger token budget for reasoning models |
| `agents/coordinator.py` | `fault.predicted` fires at 1 Hz → RAG + LLM call every second | 30 s cooldown per (fault, severity); survives RAG failure / non-object LLM JSON |
| `requirements.txt` | `python-multipart` missing (login import fails); `bcrypt` unpinned (5.x breaks passlib) | added / pinned |
| `rag/retriever.py` | duplicate trailing chunk; chromadb hard import | fixed; lazy import, injectable embedder |
| `main.py` | shutdown cancelled tasks without awaiting them | `gather` before closing Redis |
| `hooks/useWebSocket.ts` | socket reconnected forever after unmount/logout | detach `onclose` in cleanup |
| `lib/api.ts` | non-2xx responses (e.g. 403) were returned as data | throws with server `detail` |
| `schemas.py` | naive `utcnow` default timestamp | timezone-aware |
| `tests/test_simulator.py` | two assertions ignored random throttle (~12 % flaky) | thresholds account for the 0.85–1.15 range |

**Tests: 35 → 329 backend, 0 → 102 frontend.** Backend integration tests run the real app against SQLite + fakeredis,
including the full lifespan (simulator → agents → RAG/LLM → WebSocket) and real WebSocket handshakes. Verified on the pinned
`requirements.txt` versions and on current releases; 14 re-introduced bugs were all caught by the suite.

**Known limitations:** the first 1–2 ticks of a compressor stall read `bearing_wear` (vibration-only) before the signature
completes; the twin is EGT-only so bearing wear does not raise twin drift; TimescaleDB hypertable creation is not covered by
tests (needs a real Timescale server); the Groq call was not exercised live.

### v1.2 — Backend test suite added (Nov 23, 2026)

**35 tests added across 6 modules:**

| Test file | Modules covered | Tests |
|-----------|-----------------|-------|
| `tests/test_anomaly.py` | `app.ml.anomaly` (AnomalyDetector, RULPredictor) | 9 |
| `tests/test_digital_twin.py` | `app.twin.digital_twin` (DigitalTwin physics model) | 6 |
| `tests/test_simulator.py` | `app.simulator.engine` (EngineSimulator, FaultScenario) | 10 |
| `tests/test_auth.py` | `app.auth.auth` (hash/verify/JWT/RBAC) | 4 |
| `tests/test_schemas.py` | `app.models.schemas` (Pydantic models) | 4 |
| `tests/test_config.py` | `app.config` (Settings) | 2 |

| Change | File | Detail |
|--------|------|--------|
| Added `tests/__init__.py` | `backend/tests/` | Tests package marker |
| Added `tests/conftest.py` | `backend/tests/` | Shared fixtures: anomaly_detector, rul_predictor, digital_twin, simulator |
| Added test suite | `backend/tests/` | 35 tests, all passing; chromadb/sentence-transformers RAG tests excluded (no MSVC build tools) |

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
