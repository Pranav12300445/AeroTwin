# 🛠️ AeroTwin — Software Prerequisites & Setup Guide

> [!IMPORTANT]
> Complete all installations below **before** starting development. Estimated setup time: **30–45 minutes**.

---

## ✅ Already Installed on Your System

| Software | Version Detected | Status |
|---|---|---|
| **Python** | 3.13.6 | ✅ Ready |
| **pip** | 26.2.1 | ✅ Ready |
| **Node.js** | v24.15.0 | ✅ Ready |
| **npm** | 12.2.2 | ✅ Ready |
| **Git** | 2.52.0 | ✅ Ready |
| **Docker** | 29.6.2 | ⚠️ Installed, but config file has permission issue (see fix below) |
| **VS Code** | 1.147.0 | ✅ Ready |

---

## ❌ Need to Download & Install

### 1. 🐳 Docker Desktop (Fix Required)
Docker is installed but has a config permission issue. 

**Fix:**
1. Open **Docker Desktop** application (search in Start menu)
2. If it asks to fix config, let it
3. Or manually delete/reset: `del C:\Users\prana\.docker\config.json` then restart Docker Desktop
4. Verify Docker Compose works:
   ```powershell
   docker compose version
   ```
   > You need Docker Compose V2 (comes built-in with Docker Desktop). Your current install may have an older version — update Docker Desktop if `docker compose` doesn't work.

**Download (if update needed):** https://docs.docker.com/desktop/setup/install/windows-install/

---

### 2. 🔑 Groq API Key (Free)
The LLM brain behind all 4 agents. **Free tier = 30 req/min, 14,400 req/day.**

1. Go to https://console.groq.com/keys
2. Sign up / log in (Google or GitHub)
3. Click **"Create API Key"**
4. Copy the key and save it — you'll put it in a `.env` file later

---

### 3. 📦 Python Packages (pip install)
These will be installed via `requirements.txt` during project setup, but here's what's needed:

```
# Core Backend
fastapi==0.115.*
uvicorn[standard]==0.32.*
websockets==14.*
pydantic==2.*
python-dotenv==1.*

# Agents
autogen-agentchat==0.4.*
autogen-ext[openai]==0.4.*

# ML / Data Science
torch==2.5.*
numpy==2.*
pandas==2.*
scikit-learn==1.6.*

# Database
asyncpg==0.30.*
sqlalchemy[asyncio]==2.*
psycopg2-binary==2.9.*

# RAG
chromadb==0.5.*
sentence-transformers==3.*

# Messaging
redis==5.*

# Auth
python-jose[cryptography]==3.3.*
passlib[bcrypt]==1.7.*

# Logging
structlog==24.*
```

> [!NOTE]
> Don't install these manually now — we'll create a `requirements.txt` and install them all at once during project scaffolding.

---

### 4. 📦 Node.js Packages (npm install)
For the React/Next.js dashboard. Will be set up during project scaffolding:

```
# Core
next
react
react-dom
typescript
@types/react

# Charts & Visualization
recharts          # Telemetry gauges/charts
d3                # SVG engine schematic

# Real-time
socket.io-client  # WebSocket connection

# Auth UI
jwt-decode        # Decode JWT tokens client-side

# UI Components
tailwindcss       # Styling
lucide-react      # Icons
```

> [!NOTE]
> Don't install these manually now — we'll run `npx create-next-app` and `npm install` during project scaffolding.

---

### 5. 🧩 VS Code Extensions (Recommended)

Install these for a better development experience:

| Extension | Purpose |
|---|---|
| **Python** (ms-python.python) | Python IntelliSense, debugging |
| **Pylance** (ms-python.vscode-pylance) | Fast Python language server |
| **Docker** (ms-azuretools.vscode-docker) | Docker file support, container management |
| **Thunder Client** (rangav.vscode-thunder-client) | API testing (like Postman) |
| **ES7+ React Snippets** (dsznajder.es7-react-js-snippets) | React code snippets |
| **Tailwind CSS IntelliSense** (bradlc.vscode-tailwindcss) | Tailwind autocomplete |

---

## 🏗️ Infrastructure (Runs via Docker — No Manual Install)

These services run inside Docker containers. **You do NOT need to install them on your machine:**

| Service | Runs In Docker | Why |
|---|---|---|
| **TimescaleDB** | `timescale/timescaledb:latest-pg16` | Time-series database for telemetry + asset history |
| **Redis** | `redis:7-alpine` | Message broker for agent event pub/sub |
| **ChromaDB** | Runs in-process (Python) | Vector store for RAG — no separate container needed |

---

## 📋 Pre-Flight Checklist

Run these commands to verify everything is ready:

```powershell
# 1. Python
python --version          # Expect: 3.13.x  ✅

# 2. pip
pip --version             # Expect: 26.x    ✅

# 3. Node.js
node --version            # Expect: v24.x   ✅

# 4. npm
npm --version             # Expect: 12.x    ✅

# 5. Git
git --version             # Expect: 2.52.x  ✅

# 6. Docker (fix first!)
docker --version          # Expect: 29.x
docker compose version    # Expect: v2.x (MUST work)

# 7. Groq API key
# Verify at: https://console.groq.com/keys
```

---

## ⚡ Quick Setup After Downloads

Once everything above is installed and verified:

```powershell
# Navigate to project
cd E:\AeroTwin

# Initialize git repo
git init

# We'll scaffold the project structure next!
```

> [!TIP]
> **The only thing you need to manually download/set up is:**
> 1. Fix Docker Desktop (or update it)
> 2. Get a free Groq API key
> 
> Everything else is already on your system or will be installed via package managers during project scaffolding.

