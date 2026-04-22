# Deployment Plan — Expense Tracker

## Overview

Migrate the expense tracker from a local single-user application to a deployed
multi-tenant web product. Each user gets their own isolated Postgres schema,
so all existing business logic stays untouched.

**Target stack:**
| Layer | Service |
|---|---|
| Frontend | Vercel |
| Backend API | Railway |
| Database | Neon (PostgreSQL) |
| Auth | Supabase Auth |
| ETL (email sync) | Railway background worker |

> **Auth note:** Originally designed with Clerk. Migrated to Supabase Auth on
> branch `release/supabase-auth` because Clerk requires DNS-verified custom
> domains — incompatible with `*.vercel.app`. See `plan/supabase_auth_migration.md`.

---

## Architecture

```
Supabase Auth (JWT tokens — RS256, JWKS endpoint)
       │
       ▼
Vercel (React + Vite frontend)
       │  Authorization: Bearer <supabase_jwt>  on every request
       ▼
Railway (FastAPI backend)
       │  auth.py fetches JWKS from SUPABASE_URL/auth/v1/.well-known/jwks.json
       │  Decodes JWT → extracts user_id (UUID sub claim)
       │  Sets: SET search_path = u_<user_id> on every DB session
       ▼
Neon (Single PostgreSQL instance)
       ├── u_a1b2c3d4_0000_.../ ← your schema
       │     ├── transactions
       │     ├── categories
       │     ├── user_settings
       │     └── ...all other tables
       ├── u_xyz789_0000_.../   ← another user's schema
       │     └── ...
       └── ...
```

Each user's data lives in a dedicated Postgres schema. No data can ever leak
between users. All SQLAlchemy models and routers are unchanged from single-user.

---

## Implementation Status

| Component | Status | Notes |
|---|---|---|
| Supabase project | ✅ Created | `thfdkxcvazmiajtnudgo.supabase.co` |
| `backend/app/auth.py` | ✅ Done | Uses JWKS+RS256 (via `SUPABASE_URL`) |
| `backend/app/database.py` | ✅ Done | Schema-per-user, `get_db_for_user` |
| `backend/app/routers/provision.py` | ✅ Done | Idempotent schema init |
| `backend/app/routers/gmail_setup.py` | ✅ Done | Save/verify IMAP creds |
| All other routers wired with auth | ✅ Done | All use `get_current_user_id` |
| `frontend/src/lib/supabase.js` | ✅ Done | Supabase client |
| `frontend/src/api/axios.js` | ✅ Done | Attaches session token |
| `frontend/src/App.jsx` | ✅ Done | Session-based route guard |
| `frontend/src/pages/AuthPage.jsx` | ✅ Done | Supabase Auth UI |
| `frontend/.env.development` | ✅ Done | Valid anon key set |
| `frontend/.env.production` | ❌ Not created | Needed for Vercel deploy |
| CORS in `main.py` | ✅ Done | `my-expense-tacker.vercel.app` is the intended URL |
| Railway deployment | ❌ Pending | Phase 5 below |
| Vercel deployment | ❌ Pending | Phase 6 below |
| Supabase URL config | ❌ Pending | Add Vercel URL to allowed origins |

---

## Phase 1 — Fix Pre-Deploy Issues (Do This First)

### 1.1 ~~Fix the Supabase anon key~~ ✅ Done

`frontend/.env.development` now has a valid `eyJ...` JWT anon key.

### 1.2 Verify Supabase auth settings

In the Supabase dashboard → **Authentication → URL Configuration**:
- **Site URL:** (leave as localhost for now, update after Vercel deploy)
- **Redirect URLs:** add `http://localhost:5173` for local dev

---

## Phase 2 — Database (Neon)

### Already provisioned

The Neon project is already configured in `backend/.env`:

```
PG_HOST=ep-damp-cloud-aoqyz3dh.c-2.ap-southeast-1.aws.neon.tech
DB_NAME=neondb
DB_USER=neondb_owner
```

No manual schema setup needed — schemas are created automatically by `/provision`
on each user's first login.

### If starting from scratch

1. Go to https://neon.tech → **New Project**
2. Name it `expense-tracker`, pick the closest region
3. Copy the connection string, split into `PG_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS`
4. For asyncpg: the URL prefix must be `postgresql+asyncpg://`

---

## Phase 3 — Backend Reference (Already Implemented)

These files are already complete. This section documents what they do.

### `backend/app/auth.py`

Decodes Supabase JWTs on every request using **JWKS over RS256** (not HS256
as originally planned — RS256 is more secure since the secret never leaves
Supabase).

Requires one env var: `SUPABASE_URL` (used to construct the JWKS endpoint URL).
The JWKS response is cached in-process after the first request.

```
GET {SUPABASE_URL}/auth/v1/.well-known/jwks.json  →  RSA public keys
```

### `backend/app/database.py`

- `get_db_for_user(user_id)` — sets `search_path` to `u_<uuid>` schema
- `provision_user_schema(user_id)` — `CREATE SCHEMA IF NOT EXISTS`, runs
  `metadata.create_all`, seeds default categories

### `backend/app/routers/provision.py`

`POST /provision` — idempotent, called by frontend on every login.

### `backend/app/routers/gmail_setup.py`

- `POST /gmail-setup/save` — tests IMAP connection, saves encrypted credentials
- `POST /gmail-setup/mark-ready` — marks the user as fully configured
- `GET /gmail-setup/status` — frontend polls this to decide whether to show wizard

### Backend env vars summary

| Variable | Description | Where it comes from |
|---|---|---|
| `PG_HOST` | Neon host | Neon dashboard |
| `DB_NAME` | Database name | Neon dashboard |
| `DB_USER` | DB username | Neon dashboard |
| `DB_PASS` | DB password | Neon dashboard |
| `SUPABASE_URL` | Supabase project URL | Supabase dashboard → Project Settings → API |
| `ENCRYPTION_KEY` | 32-byte key for Gmail app password encryption | Generate once, keep secret |
| `GEMINI_API_KEY` | LLM for chatbot | Google AI Studio |

---

## Phase 4 — Frontend Reference (Already Implemented)

These files are already complete. This section documents what they do.

### Auth flow

1. `App.jsx` calls `supabase.auth.getSession()` on mount, subscribes to
   `onAuthStateChange` — `session` state is `undefined` (loading) → `null`
   (logged out) → `Session` object (logged in)
2. While `session === undefined`, nothing renders (prevents sign-in flash)
3. Unauthenticated users are redirected to `/sign-in` (renders `AuthPage.jsx`)
4. On login, `AppInitializer` calls `POST /provision` then checks
   `/gmail-setup/status` — redirects to `/setup` if not configured

### `frontend/src/api/axios.js`

The axios interceptor runs `supabase.auth.getSession()` before every request
and attaches the access token. The interceptor is set at module level (not
inside `useApi()`), so it's attached once and never stacks.

### Frontend env vars summary

| Variable | Description |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public JWT key (starts with `eyJ`) |
| `VITE_API_URL` | Backend base URL |

---

## Phase 5 — Railway Deployment (Backend)

1. Merge `release/supabase-auth` → `main` (or deploy directly from the branch)
2. In Railway: **New Project → Deploy from GitHub repo**
3. Select the repo, set **root directory** to `backend/`
4. Set the **start command**:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Add the following **environment variables** in Railway's dashboard:

| Variable | Value |
|---|---|
| `PG_HOST` | `ep-damp-cloud-aoqyz3dh.c-2.ap-southeast-1.aws.neon.tech` |
| `DB_NAME` | `neondb` |
| `DB_USER` | `neondb_owner` |
| `DB_PASS` | (from Neon dashboard) |
| `SUPABASE_URL` | `https://thfdkxcvazmiajtnudgo.supabase.co` |
| `ENCRYPTION_KEY` | `5846c3b7f0bbf293a089837449f6989e` (or rotate) |
| `GEMINI_API_KEY` | (from Google AI Studio) |

6. Railway auto-assigns a public URL — copy it for Phase 6

**Verify:** `curl https://YOUR_RAILWAY_URL/health` should return `{"status": "ok"}`

---

## Phase 6 — Vercel Deployment (Frontend)

### 6.1 Create `frontend/.env.production`

```
VITE_SUPABASE_URL=https://thfdkxcvazmiajtnudgo.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...    ← real anon key from Supabase dashboard
VITE_API_URL=https://YOUR_APP.railway.app
```

Do **not** commit this file (it is in `.gitignore`). Set these as Vercel
environment variables instead (step 4 below).

### 6.2 Deploy

1. Push code to GitHub
2. In Vercel: **New Project → Import Git Repository**
3. Set **framework preset** to Vite, **root directory** to `frontend/`
4. Add **environment variables** in Vercel's dashboard:

| Variable | Value |
|---|---|
| `VITE_SUPABASE_URL` | `https://thfdkxcvazmiajtnudgo.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | anon key from Supabase dashboard |
| `VITE_API_URL` | Railway URL from Phase 5 |

5. Click **Deploy**
6. Note the Vercel URL (e.g. `https://expense-tracker.vercel.app`)

---

## Phase 7 — Post-Deploy Configuration

After both services are live, two cross-references must be updated.

### 7.1 CORS in `backend/app/main.py` — already set

`main.py` already has `https://my-expense-tacker.vercel.app` in `allow_origins`.
No change needed here — just make sure the Vercel project is deployed under that
exact URL when you create it in Phase 6.

### 7.2 Update Supabase Auth URLs

In Supabase dashboard → **Authentication → URL Configuration**:
- **Site URL:** `https://YOUR_APP.vercel.app`
- **Redirect URLs:** `https://YOUR_APP.vercel.app/**` and `http://localhost:5173`

Without this, OAuth (Google) and magic link emails will redirect to the wrong URL.

---

## Phase 8 — Smoke Test Checklist

Run these after all three services are live and cross-configured:

- [ ] Visiting the Vercel URL shows the Supabase Auth sign-in page (not a blank screen)
- [ ] Sign up with email → receive confirmation email → click link → redirected to app
- [ ] Dashboard loads (empty state is fine — no transactions yet)
- [ ] Railway logs show `POST /provision` returning `{"status": "ready"}`
- [ ] Gmail setup wizard appears on first login (since `imap_configured = false`)
- [ ] After completing wizard, `/gmail-setup/status` returns `{"configured": true}`
- [ ] Add a transaction → it persists after page refresh
- [ ] Sign out → redirected to `/sign-in`
- [ ] Sign in again → same data visible (schema preserved)
- [ ] Two different accounts → completely separate dashboards (schema isolation)
- [ ] Google sign-in (if enabled) → works end-to-end

---

## Local Development

```bash
# backend/.env — already configured, no changes needed for local dev

# frontend/.env.development — fix the anon key (Phase 1.1), then:
cd frontend && npm run dev

# backend:
cd backend && uvicorn app.main:app --reload
```

The local backend points to Neon (cloud DB) even in development — this is
intentional so local and production share the same schema structure.

---

## Cost Summary

| Service | Free Tier | When You'd Pay |
|---|---|---|
| Vercel | Unlimited for personal projects | Never (personal use) |
| Railway | $5/month free credit | If compute exceeds ~500 hours/month |
| Neon | 0.5 GB, ~500–1000 users | $19/month at scale |
| Supabase | 50,000 MAU free | $25/month beyond 50k users |
| **Total** | **~$0/month** | **~$44/month at real scale** |

Supabase is notably more generous than Clerk (50k vs 10k MAU free tier).

---

## Open Questions / Future Work

- **OAuth2 migration for Gmail**: The App Password approach works well at small
  scale. Beyond ~50 users, Google OAuth2 + Gmail API removes the 4-step manual
  setup. Requires a Google Cloud project and app verification (~4–6 weeks).
- **Email backfill UX**: A Gmail filter/search query to bulk-select past bank
  emails for users with months of history (e.g. `from:alerts@hdfcbank.com`).
- **Mobile (PWA)**: `manifest.json` + service worker after web deploy is stable.
- **Capacitor**: Native app wrapper if App Store presence is needed — no
  frontend rewrite required.
