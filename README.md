# Travel Itinerary Planner

A single-session, anonymous web app that turns a destination and rough dates into a generated day-by-day itinerary. See [`travel-planner-prd.md`](travel-planner-prd.md) for the full product spec and build phases.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for Postgres and Redis)

## Project Structure

```
backend/     FastAPI + SQLAlchemy
frontend/    React + Vite + TypeScript
```

## Quick Start

### 1. Start infrastructure

```bash
docker compose up -d
```

This starts Postgres 16 and Redis 7 on ports 5433 and 6379.
(Postgres uses host port 5433 so it does not conflict with a local Postgres on 5432.)

### 2. Backend setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env with your API keys as needed

uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. Health check: `GET /health`.

Tables are created automatically on first startup via SQLAlchemy (`init_db` in the app lifespan).

### 3. Frontend setup

```bash
cd frontend
npm install

cp .env.example .env

npm run dev
```

The app runs at `http://localhost:5173`.

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `REDIS_URL` | Redis connection string |
| `ITINERARY_RATE_LIMIT` | Max `POST /itinerary` per hour per trip/IP. `0` disables (local default) |
| `APP_API_TOKEN` | Service token for frontend↔backend auth |
| `SESSION_SECRET` | Key for signing session cookies |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) |
| `LLM_PROVIDER` | `anthropic` or `nvidia` |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `NVIDIA_API_KEY` | NVIDIA API key (Nemotron evaluation) |
| `GEOAPIFY_API_KEY` | Geoapify (geocoding + POI) |
| `TAVILY_API_KEY` | Tavily search fallback |
| `GEMINI_API_KEY` | Gemini image generation (Phase 3) |
| `CAMBAI_API_KEY` | Cambai TTS (Phase 4) |

See [`backend/.env.example`](backend/.env.example) for defaults.

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Backend API URL |
| `VITE_APP_API_TOKEN` | Must match backend `APP_API_TOKEN` |

See [`frontend/.env.example`](frontend/.env.example) for defaults.

## Development

### Run tests

```bash
cd backend
pytest
```

### Lint backend

```bash
cd backend
ruff check .
```

### Build frontend

```bash
cd frontend
npm run build
```

## Phase 0 Scope

This boilerplate implements **Phase 0 (Foundation)** from the PRD:

- Postgres schema for `trip_state`, `story_sessions`, `itineraries`, `feedback`
- Redis client wrapper
- LLM provider swap abstraction (Anthropic / NVIDIA)
- App-level API token middleware and session cookie helpers
- Health endpoint with DB + Redis connectivity checks
- Minimal React frontend shell with API client

No feature endpoints or UI flows yet — those begin in Phase 1.
