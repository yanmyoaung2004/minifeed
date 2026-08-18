# MiniFeed — Full Stack Social Feed

A complete mini social feed built as a full-stack engineering challenge: users sign up / log in (email+password **or** GitHub/Google OAuth), write short posts, and read a newest-first public feed. The backend is a resilient FastAPI service (Redis cache with stale fallback, two-layer rate limiting, health-aware failover), served behind a load-balancing Nginx reverse proxy, with a polished React 19 frontend built to a design system.

Repo: `https://github.com/yanmyoaung2004/minifeed` (private)

---

## 1. Feature tour

### Authentication
- **Email + password signup/login** — passwords hashed with **Argon2id** (`pwdlib[argon2]`), JWT (HS256) with 30-minute expiry, `sub` = user id, `exp` = UTC expiry.
- **Login accepts an email *or* a username** (case-insensitive). Missing user and wrong password return the identical `401 {"detail":"Invalid credentials"}` — no user enumeration.
- **Duplicate signup** is rejected with field-specific `409` (`"email already registered"` / `"username already taken"`); usernames are unique case-insensitively, so `TestUser` + `testuser` can never collide into a `500`.
- **OAuth sign-in (GitHub + Google)** — backend-initiated Authorization Code flow (Authlib). CSRF-safe HMAC-signed `state` (nonce + provider + 10-min expiry). Existing email → account **merged** (both login methods work); new email → account created with a deduplicated username and a `NULL` password. OAuth-only accounts can **never** log in by password (strict NULL guard).
- **`GET /auth/me`** returns the authenticated user.
- **Token bridge** — the OAuth callback redirects to the SPA with `?token=<jwt>`; the frontend captures it synchronously (before any router navigation), stores it, and strips it from the URL with `history.replaceState` so the token never lingers in history/referrers.

### Feed
- **`GET /posts`** — public, newest first (`ORDER BY created_at DESC`), authors joined eagerly (no N+1).
- **`POST /posts`** — Bearer-authenticated, content 1–500 chars (stripped, whitespace-only rejected), `409`-safe transaction with rollback.
- **Search posts by keyword** — `GET /posts?search=<term>` filters content case-insensitively (wildcards `%`/`_` escaped), newest first; blank search returns the full feed; queries >100 chars are rejected with `422`. Search results bypass the feed cache (always fresh from the DB).
- **Frontend feed resilience** — skeletons on first load, empty state ("No posts yet — be the first to share!"), error state with Retry, and a **stale-data banner**: if a refresh fails after posts have loaded, the last-known-good posts stay on screen with "Couldn't refresh — showing earlier posts."

### Performance & reliability
- **Redis feed cache (cache-aside)** — `feed:v1` + `feed:v1:ts`, TTL 30s, with `X-Cache: HIT/MISS/STALE`, `ETag` (SHA-256) + `If-None-Match` → `304 Not Modified`, `Cache-Control: public, max-age=30`, and `Warning: 110 - "Response is stale"` on stale serves.
- **Failure ladder** — Redis down → straight-to-DB; DB down + cache present → stale serve (200); both down → `503 {"detail":"Service temporarily unavailable"}`. Zero unhandled outages.
- **Pre-warm** — the feed cache is populated on startup.
- **Two backend replicas** behind nginx **round-robin** with passive health checks (`max_fails=2 fail_timeout=10s`) — stopping one replica causes zero user-visible errors.

### Security hardening
- **Rate limiting, two layers**: SlowAPI app-level (signup 5/min/IP, login 5/min/IP, posts 10/min/user — posts keyed by **user id**, not IP, so one NAT'd user can't block another) plus an Nginx `limit_req` (30/min/IP, burst 10) at the edge. Every `429` carries `Retry-After` + a JSON body.
- **Input validation** at the Pydantic layer; no raw SQL; no stack traces in any response.
- **10 KB request-body cap** at the Nginx boundary (buffer-overflow/DoS mitigation).
- **Non-root** execution inside the backend container.
- **`GET /health`** — strict readiness probe (Postgres `SELECT 1` + Redis `PING`): `200` only when both are up, else `503` with per-dependency state.

### Frontend UX (built to `DESIGN.md`)
- Design system: pure-white surfaces, burnt-orange accent (OKLCH), Inter + Fraunces logotype, OKLCH tokens.
- Every state is specified: loading, empty, error, submitting, stale, rate-limited, token-expired, OAuth errors (cancelled / failed / not-configured → friendly, dismissible banners).
- Accessibility: ARIA `role=alert`, `aria-live` counters, visible focus rings, `prefers-reduced-motion`, labels bound to inputs.

---

## 2. Architecture

```
                          ┌──────────────────────────────────────────────┐
  Browser ──────────────► │ Nginx (:80)  SPA · /api reverse proxy        │
                          │              · round-robin LB · limit_req 30r/m│
                          └───────────────┬──────────────────────────────┘
                                          │  /api → backend/ (prefix stripped)
                                          ▼
                              ┌───────────────────────┐   GET /health
                              │ backend-1 :8000       │◄── docker HEALTHCHECK
                              │ backend-2 :8000       │   (Postgres + Redis pings)
                              └───────────┬───────────┘
                                          │
                         ┌────────────────┴────────────────┐
                         │ Redis 7   (shared feed cache)    │  PostgreSQL 16 (shared volume)
                         └─────────────────────────────────┘
```

**Two run modes**

| Mode | Backend | Frontend | Cache | DB |
|---|---|---|---|---|
| **Local** | `uvicorn` on :8000 | Vite dev on :5173 | Redis optional (auto-bypass) | SQLite |
| **Docker** | 2× FastAPI behind nginx | nginx-served SPA on :80 | Redis container | Postgres 16 |

**Request lifecycle (feed):**
`GET /posts` → nginx → backend → Redis check → HIT: serve with `X-Cache: HIT` (no DB) · MISS: query Postgres (author eagerly loaded) → write Redis → serve with `X-Cache: MISS` · DB failure: serve stale cache with `X-Cache: STALE` + `Warning`.

**Failure ladder:**

| Condition | Result |
|---|---|
| Redis down | `GET /posts` works, straight from DB (bypass logged) |
| DB down, cache has data | `200` stale feed, `X-Cache: STALE`, `Warning: 110` |
| DB down, cache empty | `503 {"detail":"Service temporarily unavailable"}` |
| One backend replica down | nginx routes around it (`max_fails=2`) |

---

## 3. Repository structure

```
.
├── backend/                        # FastAPI application
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings (env-driven)
│   │   │   ├── security.py         # Argon2 + JWT encode/decode
│   │   │   ├── dependencies.py     # get_current_user (HTTPBearer)
│   │   │   ├── cache.py            # async Redis cache-aside + stale fallback
│   │   │   ├── rate_limit.py       # SlowAPI limiter + 429 handler
│   │   │   └── oauth.py            # Authlib registry, HMAC state, token/userinfo
│   │   ├── db/
│   │   │   ├── database.py         # engine, session, FK pragma
│   │   │   └── models.py           # User (nullable password, oauth cols), Post
│   │   ├── schemas/                # Pydantic v2 models (auth, post)
│   │   ├── routers/                # auth, oauth, posts, health
│   │   └── main.py                 # app factory, lifespan (schema retry + pre-warm)
│   ├── tests/                      # pytest suite (78 tests)
│   ├── Dockerfile                  # multi-stage, non-root, HEALTHCHECK
│   ├── pyproject.toml / uv.lock    # uv-managed project
│   └── requirements.txt            # pip fallback
├── frontend/                       # React 19 + TypeScript + Vite
│   ├── src/
│   │   ├── api/                    # axios client (interceptors) + typed endpoints
│   │   ├── components/             # PostComposer, PostCard, skeletons, states, OAuthButtons
│   │   ├── context/                # AuthContext (token lifecycle + /auth/me)
│   │   ├── hooks/                  # usePosts (stale-data retention)
│   │   ├── pages/                  # AuthPage, FeedPage
│   │   └── __tests__/              # Vitest + RTL (22 tests)
│   ├── Dockerfile                  # multi-stage node build → nginx
│   └── nginx.conf                  # SPA + proxy + LB + rate limit + 10k cap
├── postman/                        # collection + environment
├── docker-compose.yml              # postgres · redis · backend ×2 · frontend
├── README.md
└── .gitignore
```

---

## 4. Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.12+ (tested 3.13) | backend |
| Node.js | 20+ | frontend |
| uv | latest | recommended backend tooling (pip also works) |
| Redis | 7 | optional local cache; required in Docker mode |
| Docker + Compose | 24+ / v2+ | Docker path only |

---

## 5. Quick start (Docker — everything, one command)

```bash
docker compose up --build
# optional root .env for SECRET_KEY / OAuth creds (see §7)
```

Open `http://localhost`. Sign up, log in, post — it's a full stack: nginx SPA + 2× FastAPI + Postgres + Redis.

## 6. Local development

### Backend

```bash
cd backend
cp .env.example .env          # optional; defaults work

# Option A — uv (recommended)
uv venv
uv sync
uv run uvicorn app.main:app --reload --reload-include "*.env"

# Option B — pip (classic)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-include "*.env"
```

- Runs at `http://localhost:8000`; interactive API docs at `http://localhost:8000/docs`.
- `--reload-include "*.env"` makes `.env` edits hot-reload (plain `--reload` does not watch env files).
- **Redis is optional locally** — the cache degrades to database reads when unreachable. To enable caching: `docker run -d --name minifeed-redis -p 6379:6379 redis:7-alpine`.
- **Schema note:** if the `User`/`Post` models ever change, delete `backend/app.db` once (SQLite won't migrate existing tables); it regenerates on startup.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- Runs at `http://localhost:5173`.
- Vite proxies `/api/*` (prefix stripped) and `/auth/oauth/*` to the backend — no CORS friction in development.

### Tests

```bash
cd backend && uv run pytest          # 78 tests
cd frontend && npm test              # 22 tests (Vitest + RTL)
```

---

## 7. Environment variables

### Backend (`backend/.env`)

| Variable | Description | Default | Required |
|---|---|---|---|
| `SECRET_KEY` | JWT signing secret (≥32 bytes) | dev fallback | yes in prod |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime | `30` | no |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./app.db` | no |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` | no |
| `FEED_CACHE_TTL` | Feed cache TTL (seconds) | `30` | no |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth app | empty | OAuth |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth client | empty | OAuth |
| `OAUTH_CALLBACK_BASE` | Callback base (local: `:8000`, Docker: `http://localhost`) | `http://localhost:8000` | OAuth |
| `FRONTEND_URL` | Success-redirect origin | `http://localhost:5173` | OAuth |
| `FIREBASE_*` | Placeholders for a future mobile integration | empty | no |

### Docker Compose (`root .env` next to `docker-compose.yml`, optional)

`SECRET_KEY`, `POSTGRES_USER` (default `minifeed`), `POSTGRES_PASSWORD` (default `minifeed`), `POSTGRES_DB` (default `minifeed`), `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. Every value has a working default — nothing is required to start.

---

## 8. API reference

Base URL: `http://localhost:8000` (local) or `http://localhost/api` (Docker/nginx).

### `GET /health`
| Code | Body |
|---|---|
| 200 | `{"status":"healthy","database":"ok","cache":"ok"}` |
| 503 | `{"status":"degraded","database":"ok"|"error","cache":"ok"|"error"}` |

### `POST /auth/signup`
Request: `{"username":"janedoe","email":"jane@example.com","password":"secret123"}`
| Code | Body |
|---|---|
| 201 | `{"id":1,"username":"janedoe","email":"jane@example.com","created_at":"..."}` |
| 409 | `{"detail":"email already registered"}` / `{"detail":"username already taken"}` |
| 422 | Pydantic field errors (invalid email, username <3, password <6) |
| 429 | `{"detail":"Rate limit exceeded: 5 per 1 minute"}` + `Retry-After` |

### `POST /auth/login`
Request: `{"identifier":"jane@example.com","password":"secret123"}` (identifier accepts email **or** username)
| Code | Body |
|---|---|
| 200 | `{"access_token":"<jwt>","token_type":"bearer"}` |
| 401 | `{"detail":"Invalid credentials"}` (identical for unknown user / wrong password) |
| 429 | rate limited |

### `GET /auth/me` — Bearer required
200 → `{"id":1,"username":"janedoe","email":"...","created_at":"..."}` · 401 if missing/expired/invalid token.

### `GET /auth/oauth/providers`
200 → `{"providers":["github","google"]}` (only configured ones).

### `GET /auth/oauth/{provider}` — `github` | `google`
302 → provider consent URL with HMAC-signed `state`. 302 → `FRONTEND_URL/login?error=not_configured` if unconfigured.

### `GET /auth/oauth/{provider}/callback`
Success → 302 `FRONTEND_URL?token=<jwt>`. Errors → 302 `FRONTEND_URL/login?error=denied|invalid`.

### `GET /posts`
200 → array of `{"id":1,"content":"...","created_at":"2026-…+00:00","author":{"id":1,"username":"janedoe"}}`, **newest first**. Optional query param `search=<term>` filters by keyword (case-insensitive; `%`/`_` escaped; ≤100 chars else 422). Headers: `X-Cache: HIT|MISS|STALE` (full feed only — searches bypass the cache), `ETag`, `Cache-Control: public, max-age=30`, possibly `Warning: 110`. `304 Not Modified` when `If-None-Match` matches.

### `POST /posts` — Bearer required
Request: `{"content":"My first post!"}` (1–500 chars, stripped)
| Code | Body |
|---|---|
| 201 | full post object (above) |
| 401 | `{"detail":"Not authenticated"}` + `WWW-Authenticate: Bearer` |
| 422 | empty / whitespace-only / >500 chars |
| 429 | `{"detail":"Rate limit exceeded: 10 per 1 minute"}` + `Retry-After` |

---

## 9. Authentication deep dive

**Password flow:** signup hashes with Argon2id → store. Login looks up by email **or** username (case-insensitive) → `verify_password` → generic 401 on any failure. Argon2 verification never throws on a `NULL` password (OAuth account) — it returns `401 Invalid credentials` and the account type is never leaked.

**OAuth flow:**
```
AuthPage "Continue with GitHub"
  → GET /auth/oauth/github
  → backend signs state = base64({nonce, provider, exp:+600s}) . HMAC-SHA256(secret)
  → 302 → GitHub consent
  → GitHub → /auth/oauth/github/callback?code=…&state=…
  → verify HMAC signature + expiry + provider binding  (fail → ?error=invalid)
  → exchange code (server-side client_secret) → fetch userinfo (+ /user/emails if private)
  → find user by email → link oauth_provider/oauth_id; else create
      (username deduped: "johndoe" → "johndoe2", hashed_password = NULL)
  → issue app JWT → 302 → FRONTEND_URL?token=<jwt>
```
- The `state` is HMAC-signed with the server secret → **tampering/expiry/provider-swap all fail closed**.
- Account merging: an OAuth email matching an existing password account upgrades it to support *both* login methods.
- Frontend token bridge: the SPA reads `?token=` synchronously (before router navigation can strip it), persists to `localStorage`, and `history.replaceState` cleans the URL.

---

## 10. Caching deep dive

**Read path** (`GET /posts`):
1. `get_feed()` → Redis (`feed:v1` payload + `feed:v1:ts` timestamp, both kept 24h for stale serving).
2. Fresh (age ≤ TTL) → `200` + `X-Cache: HIT` (no DB).
3. Miss / stale → DB query → populate Redis (write-through) → `200` + `X-Cache: MISS`.
4. DB failure → if any cached payload exists → `200` + `X-Cache: STALE` + `Warning: 110`; else `503`.

**Write path:** successful `POST /posts` → `invalidate_feed()` deletes both keys → next read repopulates.

**Conditional requests:** `ETag` = SHA-256 of the JSON body (quoted). `If-None-Match` is honored on every path (HIT, MISS-refresh, STALE) → `304` with empty body. `Cache-Control: public, max-age=30` mirrors the TTL.

**Search:** `GET /posts?search=` bypasses the cache entirely (searches are ephemeral and would pollute the single feed key) and queries Postgres directly, newest first.

**Resilience:** every Redis call is wrapped — on any error the cache is bypassed (logged, never crashes the request). The feed is pre-warmed at startup. Redis is a single shared store across both replicas, so HITs are consistent regardless of which backend serves.

---

## 11. Rate limiting deep dive

| Endpoint | Limit | Key | Layer |
|---|---|---|---|
| `POST /auth/signup` | 5 / minute | client IP | SlowAPI (app) |
| `POST /auth/login` | 5 / minute | client IP | SlowAPI (app) |
| `POST /posts` | 10 / minute | **authenticated user id** | SlowAPI (app) |
| `/api/*` | 30 / minute (burst 10) | client IP | nginx `limit_req` |

- App-layer limits work in every run mode (local and Docker); nginx adds a global edge cap in Docker mode.
- Post creation is keyed by **user id** (from the JWT) so users behind the same NAT don't throttle each other; a garbage token falls back to IP for keying and is rejected by auth anyway.
- Every `429` returns `Retry-After: 60` + `{"detail":"Rate limit exceeded: …"}`.
- Known limitation: app counters are in-memory **per process** — restart resets them; multi-replica needs a shared store.

---

## 12. Frontend deep dive

**Pages & routing**
- `/login` — AuthPage (login/signup tabs, inline validation, OAuth buttons, error banners).
- `/feed` — ProtectedRoute → FeedPage (composer + feed + all states). No token → redirect to `/login` (spinner first).
- `/` → `/feed`; everything else → `/login`.

**Axios layer** (`api/client.ts`)
- `baseURL: /api`, 10s timeout, JSON headers.
- Request interceptor attaches `Authorization: Bearer <token>` from `localStorage`.
- Response interceptor: on `401` (excluding login) clears the token and redirects to `/login`.

**State matrix (all implemented)**

| Surface | State | UI |
|---|---|---|
| Feed | initial load | 3 skeleton rows |
| Feed | loaded | newest-first cards (avatar, username, relative time, content) |
| Feed | empty | "No posts yet — be the first to share!" + CTA → focuses composer |
| Feed | load failed | error + Retry |
| Feed | refresh failed (data present) | keeps posts + "Couldn't refresh — showing earlier posts." banner |
| Composer | typing | live `n/500` counter; amber <20 left; red + blocked >500; disabled when empty/whitespace |
| Composer | submitting | "Posting…" spinner, disabled |
| Composer | 429 | "Too many requests — try again in a moment." (content preserved) |
| Auth | submitting | "Logging in…" / "Creating account…" |
| Auth | field errors | inline (email format, password ≥6, username 3–30) |
| Auth | 401 | "Invalid email or password." |
| Auth | 409 | inline under the offending field |
| Auth | network down | "Can't reach the server — check your connection." |
| OAuth | `?error=denied` | "Sign-in cancelled." |
| OAuth | `?error=invalid` | "Sign-in failed — try again." |
| OAuth | `?error=not_configured` | "This sign-in option isn't available right now." |
| Session | expired token | 401 interceptor → clear → redirect `/login` |

**Design system** — OKLCH tokens in `src/index.css`: pure-white `--bg`, burnt-orange `--primary` (white text on fills), verdigris `--accent`, `--ink`/`--muted` with AA contrast. Inter for all UI; Fraunces italic reserved for the logotype. 150–250ms state transitions, `prefers-reduced-motion` respected.

---

## 13. Testing

**Backend — pytest (71 tests, in-memory SQLite + fake Redis, no external services, ~3s)**
- auth: signup success/duplicates/validation, login success (email + username), anti-enumeration, JWT `sub`/`exp`, case-variant username guard, `/auth/me`
- posts: auth required (missing/invalid/expired token), content validation boundaries (1/500/501, whitespace), newest-first ordering, multi-author, end-to-end flow, **keyword search** (filtering + order, case-insensitivity, no-results, blank/whitespace, wildcard escaping, cache bypass, >100-char rejection)
- cache: HIT/MISS/STALE headers, ETag `304` on all paths, invalidation on POST, DB-failure stale serve, total-outage `503`, Redis-unreachable fail-open, pre-warm
- rate limit: per-IP signup/login 429 + `Retry-After`, per-user post isolation, key-function fallbacks
- health: 200 healthy / 503 degraded per dependency
- oauth: state sign/verify, tampered/expired/provider-mismatch rejection, user creation (NULL password), account merge, username dedupe, cancellation/exchange-failure redirects, NULL-password login rejection

**Frontend — Vitest + RTL (22 tests, jsdom)**
- AuthPage: tabs, inline validation, 401 banner, submitting state, 409 inline, network banner, token persistence
- FeedPage: skeletons→posts, empty, error+Retry, stale banner retaining posts, composer validation/clear/429, **debounced search refetch + search-specific empty state**
- ProtectedRoute: redirect, allow, loading
- OAuth callback: `?token=` bridge (store + URL strip + authenticate), error banners

---

## 14. API testing with Postman

1. Import `postman/ET_Verdict.collection.json` and `postman/ET_Verdict.environment.json`.
2. Select the **ET_Verdict** environment: local → `base_url=http://localhost:8000`, `api_prefix=` (empty); Docker → `base_url=http://localhost`, `api_prefix=/api`.
3. Run **Auth → POST /auth/login** first — its test script stores the JWT in `{{token}}` automatically, so every **Posts** request is pre-authorized.
4. Every request asserts HTTP status, response time < 500ms, and required JSON fields.

---

## 15. OAuth provider setup

1. **GitHub** — github.com → Settings → Developer settings → OAuth Apps → New OAuth App: Homepage URL `http://localhost:5173`, Callback URL `http://localhost:8000/auth/oauth/github/callback`. Copy the client secret immediately.
2. **Google** — console.cloud.google.com → APIs & Services → Credentials → Create OAuth client ID (Web): Authorized JS origin `http://localhost:5173`, Authorized redirect URI `http://localhost:8000/auth/oauth/google/callback`.
3. Fill `backend/.env`, restart the backend. Only configured providers render buttons.
4. **Docker mode:** use `OAUTH_CALLBACK_BASE=http://localhost` and `FRONTEND_URL=http://localhost` (callbacks arrive through nginx).

---

## 16. Design decisions

- **SQLite locally, Postgres in Docker** — the brief allows SQLite; `DATABASE_URL` switches engines with zero code change (SQLAlchemy), and Postgres is required for two replicas sharing one DB.
- **Single shared Redis cache** across replicas (consistent HITs), vs. **per-process rate-limit counters** (documented limitation).
- **`localStorage` token** — pragmatic for the challenge; production would use HttpOnly cookies + CSRF or refresh tokens.
- **Health is strict, serving is graceful** — `/health` reports 503 if Redis drops (so Docker can restart a replica), while the API itself still serves from the DB.
- **Nginx upstream** uses one `server backend:8000` entry: compose replicas share the port, and Docker DNS round-robins across the replica IPs; nginx then applies `max_fails=2` per resolved peer.

---

## 17. Known limitations & future work

**Known limitations**
- `localStorage` JWT is XSS-exposed; no refresh-token rotation.
- App-level rate-limit counters are per-process/in-memory.
- `GET /posts` is unpaginated.
- SQLite (local mode) is single-writer.
- No email verification or password reset.

**Future work**
- Refresh tokens + HttpOnly cookie sessions; Alembic migrations; pagination (keyset/cursor); Redis-backed shared rate-limit storage; WebSocket live feed; Firebase push notifications for mobile; role-based access control.
