# MiniFeed — Full Stack Social Feed

A mini social feed built for a full-stack developer challenge. Users sign up / log in (password or GitHub/Google OAuth), create short posts, and view a newest-first public feed — served by a resilient FastAPI backend and a polished React frontend.

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, SQLite (local) / PostgreSQL 16 (Docker), Redis 7, JWT (HS256), Argon2 password hashing, SlowAPI rate limiting, Authlib OAuth (GitHub + Google)
- **Frontend:** React 19, TypeScript, Vite, React Router 7, Axios, Vitest + React Testing Library
- **DevOps:** Docker, Docker Compose, Nginx (SPA serving, reverse proxy, load balancing, rate limiting)

---

## Features & architecture decisions

- **Auth:** email/password (Argon2 + JWT, 30 min expiry) *and* OAuth (GitHub/Google). OAuth uses an HMAC-signed `state` token (nonce + provider + expiry) to block CSRF; passwords are hashed with Argon2id; OAuth-only accounts have a `NULL` password and can never authenticate by password.
- **Feed caching (cache-aside + stale fallback):** `GET /posts` is cached in Redis (TTL 30s) with `X-Cache: HIT/MISS`, `ETag`/`If-None-Match` → `304 Not Modified`, and `Cache-Control: public, max-age=30`. If Redis is down the API serves straight from the database; if the **database** is down, a stale cached feed is served with `X-Cache: STALE` + `Warning: 110`; only a total outage returns `503`.
- **Rate limiting (two layers):** SlowAPI app-level limits (`/auth/signup` 5/min/IP, `/auth/login` 5/min/IP, `POST /posts` 10/min/user) in every run mode, plus an Nginx `limit_req` (30/min/IP) in Docker mode. All `429`s return `Retry-After` + a JSON body.
- **Failover routing:** Nginx round-robins across two backend replicas (`max_fails=2 fail_timeout=10s`) so a dead replica is removed from rotation; a strict `GET /health` (Postgres + Redis pings) powers container healthchecks.
- **Token storage:** the frontend stores the access token in `localStorage` — acceptable for this challenge; noted as a known limitation for production (see below).
- **Design system:** the UI is built to `DESIGN.md` — pure-white surfaces, a burnt-orange accent (OKLCH), Inter + Fraunces logotype, full state matrix (loading / empty / error / submitting / stale / rate-limited).

## Repository structure

```
.
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── core/            # config, security (argon2+JWT), cache (Redis), rate_limit, oauth
│   │   ├── db/              # SQLAlchemy engine + models (User, Post)
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── routers/         # auth, oauth, posts, health
│   │   └── main.py          # app factory, lifespan, middleware
│   ├── tests/               # pytest suite (70+ tests)
│   ├── Dockerfile
│   ├── pyproject.toml       # uv project
│   └── requirements.txt     # pip fallback (for the challenge brief)
├── frontend/                # React + TS + Vite
│   ├── src/
│   │   ├── api/             # axios client + typed endpoints
│   │   ├── components/      # PostComposer, PostCard, skeletons, states, OAuthButtons
│   │   ├── context/         # AuthContext (token lifecycle)
│   │   ├── hooks/           # usePosts (stale-data retention)
│   │   ├── pages/           # AuthPage, FeedPage
│   │   └── __tests__/       # Vitest + RTL (20 tests)
│   ├── Dockerfile
│   └── nginx.conf           # SPA + proxy + LB + rate limit
├── postman/                 # API test collection + environment
├── docker-compose.yml       # postgres + redis + 2× backend + frontend
└── .gitignore
```

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | tested on 3.13 |
| Node.js | 20+ | |
| Docker + Compose | 24+ / v2+ | only needed for the Docker path |
| uv | latest | recommended; `pip` also works |
| Redis | 7 | local dev only; Docker Compose provides it |

## Local development

### Backend

```bash
cd backend
cp .env.example .env        # then fill in values (see env table below)

# Option A — uv (recommended)
uv venv
uv sync
uv run uvicorn app.main:app --reload --reload-include "*.env"

# Option B — pip
python -m venv .venv
.venv\Scripts\activate        # Windows  ·  source .venv/bin/activate (macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-include "*.env"
```

Backend runs at `http://localhost:8000` — API docs at `http://localhost:8000/docs`.

> **Note:** Redis is optional in local mode — the cache degrades gracefully to database reads when it's unreachable. To enable caching locally, run `docker run -d --name minifeed-redis -p 6379:6379 redis:7-alpine`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`. Requests to `/api/*` and `/auth/oauth/*` are proxied to the backend by Vite, so there is no CORS friction in development.

### Tests

```bash
cd backend && uv run pytest        # backend suite
cd frontend && npm test            # frontend suite (Vitest + RTL)
```

## Docker Compose (single command)

```bash
# from the repo root
docker compose up --build
```

- Frontend (nginx): `http://localhost`
- Backend replicas: 2, behind nginx round-robin
- Services: `postgres:16-alpine`, `redis:7-alpine`, `backend` ×2, `frontend`
- OAuth vars (`GITHUB_*`, `GOOGLE_*`) are read from your shell environment or a root `.env` next to `docker-compose.yml`.

## Environment variables

Backend (`backend/.env`):

| Variable | Description | Default | Required |
|---|---|---|---|
| `SECRET_KEY` | JWT signing secret (≥32 bytes) | dev fallback | **yes** in prod |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime | `30` | no |
| `DATABASE_URL` | SQLAlchemy URL (SQLite local / Postgres in Docker) | `sqlite:///./app.db` | no |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` | no |
| `FEED_CACHE_TTL` | Feed cache TTL seconds | `30` | no |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth app | empty | OAuth only |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth client | empty | OAuth only |
| `OAUTH_CALLBACK_BASE` | Base of the OAuth callback URL | `http://localhost:8000` | no |
| `FRONTEND_URL` | Frontend origin (OAuth success redirect) | `http://localhost:5173` | no |

Compose (`root .env`, optional): `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `SECRET_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

## API endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Readiness probe (`database`, `cache`) → 200/503 |
| `POST` | `/auth/signup` | — | Create account → 201; 409 dup; 422 invalid; 429 rate-limited |
| `POST` | `/auth/login` | — | Email *or* username + password → `{access_token}`; 401 generic; 429 |
| `GET` | `/auth/me` | Bearer | Current user profile |
| `GET` | `/auth/oauth/providers` | — | Configured providers `{providers:[...]}` |
| `GET` | `/auth/oauth/{provider}` | — | Redirect to provider (signed state) |
| `GET` | `/auth/oauth/{provider}/callback` | — | Provider callback → redirect to frontend with `?token=` or `?error=` |
| `GET` | `/posts` | — | Feed, newest first; `X-Cache`, `ETag`, `304` |
| `POST` | `/posts` | Bearer | Create post (1–500 chars) → 201; 401; 422; 429 |

In Docker mode the same endpoints are reachable through nginx at `http://localhost/api/...` (the `/api` prefix is stripped by the proxy).

## OAuth setup

1. **GitHub** — github.com → Settings → Developer settings → OAuth Apps → New OAuth App: Homepage `http://localhost:5173`, Callback `http://localhost:8000/auth/oauth/github/callback`.
2. **Google** — console.cloud.google.com → APIs & Services → Credentials → OAuth client ID (Web): JS origin `http://localhost:5173`, redirect URI `http://localhost:8000/auth/oauth/google/callback`.
3. Copy the IDs/secrets into `backend/.env`, restart the backend. The frontend shows "Continue with GitHub / Google" buttons only for configured providers.
4. In Docker mode the callback bases are `http://localhost` (through nginx) — set `OAUTH_CALLBACK_BASE=http://localhost` and `FRONTEND_URL=http://localhost`.

## API testing with Postman

1. Import `postman/ET_Verdict.collection.json` and `postman/ET_Verdict.environment.json`.
2. Select the **ET_Verdict** environment. For local mode `base_url=http://localhost:8000` and `api_prefix=` (empty). For Docker mode set `base_url=http://localhost` and `api_prefix=/api`.
3. Run **Auth → POST /auth/login** first — its test script stores the JWT in `{{token}}` automatically, so **Posts** requests are pre-authorized.

## Known limitations & future enhancements

- **`localStorage` token** is vulnerable to XSS; a production app should use HttpOnly cookies + CSRF protection, or refresh tokens.
- **Rate-limit counters are in-memory per process** — a restart resets them, and multi-worker deployments would need a shared store (e.g., Redis-backed SlowAPI).
- **SQLite** (local mode) is single-writer; the Postgres Docker path is intended for multi-replica operation.
- **No pagination** on `GET /posts` yet — fine for a challenge, but long feeds should paginate.
- Future: refresh tokens, `/auth/me`-cached user sessions, Alembic migrations, pagination, WebSocket live updates.
