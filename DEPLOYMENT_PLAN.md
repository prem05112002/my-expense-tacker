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
| Auth | Clerk |
| ETL (email sync) | Railway background worker |

---

## Architecture

```
Clerk (Auth — JWT tokens)
       │
       ▼
Vercel (React + Vite frontend)
       │  Authorization: Bearer <clerk_jwt>  on every request
       ▼
Railway (FastAPI backend)
       │  Middleware decodes JWT → extracts user_id
       │  Sets: SET search_path = user_{id} on every DB session
       ▼
Neon (Single PostgreSQL instance)
       ├── user_abc123/   ← your schema
       │     ├── transactions
       │     ├── categories
       │     ├── user_settings
       │     └── ...all other tables
       ├── user_xyz789/   ← friend's schema
       │     └── ...
       └── ...
```

Each user's data lives in a dedicated Postgres schema. No data can ever leak
between users. All existing SQLAlchemy models and routers require zero changes.

---

## Phase 1 — External Accounts to Create

Before writing any code, set up the required service accounts.

- [ ] **Neon** — https://neon.tech — create a free project, copy the connection string
- [ ] **Clerk** — https://clerk.com — create an application, choose "Email + Google" as sign-in methods, copy the publishable key and secret key
- [ ] **Railway** — https://railway.app — create an account, connect GitHub
- [ ] **Vercel** — https://vercel.com — create an account, connect GitHub

---

## Phase 2 — Database (Neon)

### 2.1 Create the Neon project

1. Log in to Neon, click **New Project**
2. Name it `expense-tracker`, region closest to you
3. Copy the **connection string** — it looks like:
   `postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb`
4. Add `?sslmode=require` to the end if not already present
5. For the FastAPI asyncpg driver, replace `postgresql://` with `postgresql+asyncpg://`

### 2.2 No manual schema setup needed

Schemas are created automatically by the backend's `/provision` endpoint
(built in Phase 3) when each user signs up for the first time.

---

## Phase 3 — Backend Changes (FastAPI)

All changes are additive. No existing router or model files are modified.

### 3.1 Install new dependencies

Add to `backend/requirements.txt`:
```
clerk-backend-api    # JWT verification
PyJWT                # decode Clerk tokens
cryptography         # encrypt stored Gmail credentials
```

### 3.2 Update `backend/app/database.py`

Replace the current single-engine setup with a schema-aware session factory.
The key change is a `get_db_for_user(user_id)` dependency that sets
`search_path` to the user's schema before yielding the session.

```python
# backend/app/database.py  (updated)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("PG_HOST")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


def _safe_schema_name(user_id: str) -> str:
    """Convert a Clerk user_id like 'user_2abc123' into a valid schema name."""
    return "u_" + user_id.replace("-", "_")


async def get_db_for_user(user_id: str):
    """
    Yields an async DB session scoped to the user's Postgres schema.
    All queries within this session automatically target the right schema.
    """
    schema = _safe_schema_name(user_id)
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"SET search_path = {schema}"))
        yield session


async def provision_user_schema(user_id: str):
    """
    Called once when a new user signs up. Creates their Postgres schema
    and initialises all tables + default categories inside it.
    """
    schema = _safe_schema_name(user_id)
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(text(f"SET search_path = {schema}"))
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await session.execute(text(f"SET search_path = {schema}"))
        result = await session.execute(text("SELECT COUNT(*) FROM categories"))
        count = result.scalar()
        if count == 0:
            await session.execute(text("""
                INSERT INTO categories (name, color, is_income) VALUES
                    ('Food',          '#f87171', FALSE),
                    ('Transport',     '#60a5fa', FALSE),
                    ('Shopping',      '#c084fc', FALSE),
                    ('Bills',         '#fbbf24', FALSE),
                    ('Health',        '#4ade80', FALSE),
                    ('Salary',        '#34d399', TRUE),
                    ('Income',        '#a3e635', TRUE),
                    ('Uncategorized', '#cbd5e1', FALSE)
                ON CONFLICT (name) DO NOTHING
            """))
            await session.commit()
```

### 3.3 Add auth middleware — `backend/app/auth.py` (new file)

This file decodes the Clerk JWT on every request and makes `user_id`
available as a FastAPI dependency.

```python
# backend/app/auth.py

import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")  # set in Railway env vars

security = HTTPBearer()
_jwks_cache = None


async def _get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(CLERK_JWKS_URL)
            _jwks_cache = resp.json()
    return _jwks_cache


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    try:
        jwks = await _get_jwks()
        header = jwt.get_unverified_header(token)
        key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        payload = jwt.decode(token, public_key, algorithms=["RS256"])
        return payload["sub"]  # Clerk user_id e.g. "user_2abc123"
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
```

### 3.4 Add provisioning router — `backend/app/routers/provision.py` (new file)

This endpoint is called by the frontend immediately after a user's first login.
It is idempotent — safe to call multiple times.

```python
# backend/app/routers/provision.py

from fastapi import APIRouter, Depends
from ..auth import get_current_user_id
from ..database import provision_user_schema

router = APIRouter(prefix="/provision", tags=["Provision"])


@router.post("")
async def provision(user_id: str = Depends(get_current_user_id)):
    """
    Creates the Postgres schema + tables for a new user.
    Idempotent — safe to call on every login.
    """
    await provision_user_schema(user_id)
    return {"status": "ready", "user_id": user_id}
```

### 3.5 Wire up auth to existing routers

Each existing router's dependencies currently use `get_db`. Replace that
dependency with one that also authenticates the user.

In each router file, update the import and dependency pattern:

```python
# Before (example from transactions.py)
from ..database import get_db

@router.get("/")
async def list_transactions(db: AsyncSession = Depends(get_db)):
    ...

# After
from ..database import get_db_for_user
from ..auth import get_current_user_id

@router.get("/")
async def list_transactions(
    db: AsyncSession = Depends(
        lambda user_id=Depends(get_current_user_id): get_db_for_user(user_id)
    )
):
    ...
```

Do this for every router: `transactions`, `dashboard`, `categories`,
`staging`, `rules`, `subscription`, `trends`, `chatbot`, `sync`, `goals`.

### 3.6 Update CORS in `backend/app/main.py`

```python
# Replace the allow_origins list with your actual deployed URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-app.vercel.app",   # replace with real Vercel URL
        "http://localhost:5173",          # keep for local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the new provision router
from .routers import provision
app.include_router(provision.router)
```

### 3.7 ETL / Gmail sync — per-user credentials

Currently the ETL reads Gmail credentials from env vars (global). For
multi-user, each user configures their own Gmail account. We keep the
App Password + IMAP approach (no Google Cloud / OAuth2 complexity needed
at this scale) but store credentials securely in the database instead of
`.env` files.

**3.7.1 Model changes** — add three columns to `UserSettings`:

```python
# In backend/app/models.py — add to UserSettings class
imap_user        = Column(String,  nullable=True)  # user's Gmail address
imap_pass_enc    = Column(Text,    nullable=True)  # AES-encrypted app password
imap_configured  = Column(Boolean, default=False)  # True after verified connection
```

**3.7.2 ETL refactor** — `Etl/email_service.py` currently reads
`EMAIL_USER` / `EMAIL_PASS` as module-level globals from `config.py`.
This breaks in a multi-user model. Change `EmailService.__init__` to
accept credentials as constructor arguments:

```python
# Etl/email_service.py — updated constructor
class EmailService:
    def __init__(self, email_user: str, email_pass: str):
        self.email_user = email_user
        self.email_pass = email_pass
        self.mail = None

    def connect(self):
        self.mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        self.mail.login(self.email_user, self.email_pass)
```

The sync service then looks up the user's decrypted credentials from
`UserSettings` and passes them to `EmailService(email_user, email_pass)`.

**3.7.3 Encryption helper** — add `backend/app/crypto.py`:

```python
# backend/app/crypto.py
import os, base64
from cryptography.fernet import Fernet

_key = base64.urlsafe_b64encode(os.getenv("ENCRYPTION_KEY", "").encode()[:32].ljust(32, b"0"))
_fernet = Fernet(_key)

def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
```

### 3.8 Gmail setup verification endpoint

Add `backend/app/routers/gmail_setup.py` — called by the onboarding
wizard (Phase 4.7) to save credentials and verify the IMAP connection
actually works before marking the user as configured.

```python
# backend/app/routers/gmail_setup.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import imaplib

from ..auth import get_current_user_id
from ..database import get_db_for_user
from ..crypto import encrypt, decrypt

router = APIRouter(prefix="/gmail-setup", tags=["Gmail Setup"])

REQUIRED_LABELS = ["sync-expense-tracker", "expenses", "non-transaction"]


class GmailCredentials(BaseModel):
    email: str
    app_password: str


@router.post("/save")
async def save_and_verify(
    creds: GmailCredentials,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(lambda uid=Depends(get_current_user_id): get_db_for_user(uid)),
):
    """
    Verifies the IMAP connection is working, then saves the credentials.
    Returns which of the 3 required labels already exist in the user's Gmail.
    """
    # 1. Test the connection before saving anything
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(creds.email, creds.app_password)
    except imaplib.IMAP4.error:
        raise HTTPException(status_code=400, detail="IMAP login failed — check email and app password")

    # 2. Check which required labels already exist
    _, folders = mail.list()
    existing = [f.decode().split('"."')[-1].strip().strip('"') for f in folders]
    found_labels = [label for label in REQUIRED_LABELS if label in existing]
    mail.logout()

    # 3. Save encrypted credentials
    enc_pass = encrypt(creds.app_password)
    await db.execute(text("""
        UPDATE user_settings
        SET imap_user = :email, imap_pass_enc = :enc_pass, imap_configured = FALSE
    """), {"email": creds.email, "enc_pass": enc_pass})
    await db.commit()

    return {
        "connection": "ok",
        "labels_found": found_labels,
        "labels_missing": [l for l in REQUIRED_LABELS if l not in found_labels],
    }


@router.post("/mark-ready")
async def mark_configured(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(lambda uid=Depends(get_current_user_id): get_db_for_user(uid)),
):
    """Called by the frontend after the user confirms all labels are in place."""
    await db.execute(text("UPDATE user_settings SET imap_configured = TRUE"))
    await db.commit()
    return {"status": "configured"}


@router.get("/status")
async def setup_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(lambda uid=Depends(get_current_user_id): get_db_for_user(uid)),
):
    """Frontend polls this to know whether to show the setup wizard."""
    result = await db.execute(text(
        "SELECT imap_user, imap_configured FROM user_settings LIMIT 1"
    ))
    row = result.fetchone()
    return {
        "configured": bool(row and row.imap_configured),
        "email": row.imap_user if row else None,
    }
```

Register in `main.py`:
```python
from .routers import gmail_setup
app.include_router(gmail_setup.router)
```

---

## Phase 4 — Frontend Changes (React)

### 4.1 Install Clerk

```bash
cd frontend
npm install @clerk/clerk-react
```

### 4.2 Wrap the app in ClerkProvider — `frontend/src/main.jsx`

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ClerkProvider } from '@clerk/clerk-react'
import App from './App.jsx'
import './index.css'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ClerkProvider publishableKey={PUBLISHABLE_KEY}>
      <App />
    </ClerkProvider>
  </StrictMode>
)
```

### 4.3 Add login page and route guard — `frontend/src/App.jsx`

```jsx
import { SignedIn, SignedOut, RedirectToSignIn, SignIn } from '@clerk/clerk-react'

function App() {
  return (
    <ToastProvider>
      <Router>
        <Routes>
          {/* Public route */}
          <Route path="/sign-in/*" element={<SignIn routing="path" path="/sign-in" />} />

          {/* All other routes require auth */}
          <Route path="/*" element={
            <>
              <SignedIn>
                <Layout>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/transactions" element={<Transactions />} />
                    <Route path="/profile" element={<Profile />} />
                    <Route path="/duplicates" element={<Duplicates />} />
                    <Route path="/needs-review" element={<NeedsReview />} />
                  </Routes>
                </Layout>
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          } />
        </Routes>
      </Router>
    </ToastProvider>
  )
}
```

### 4.4 Attach JWT to every API request — `frontend/src/api/axios.js`

```js
import axios from 'axios';
import { useAuth } from '@clerk/clerk-react';

// Base instance — used in non-hook contexts
const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL,
    headers: { 'Content-Type': 'application/json' },
});

// Hook that returns an authenticated api instance
export function useApi() {
    const { getToken } = useAuth();

    api.interceptors.request.use(async (config) => {
        const token = await getToken();
        if (token) config.headers.Authorization = `Bearer ${token}`;
        return config;
    });

    return api;
}

export default api;
```

Replace direct `api` usage in pages/components with the `useApi()` hook.

### 4.5 Call `/provision` on first login

In `frontend/src/App.jsx` or a top-level component, call the provision
endpoint once after the user signs in:

```jsx
import { useAuth, useUser } from '@clerk/clerk-react';
import { useEffect } from 'react';
import { useApi } from './api/axios';

function ProvisionOnLogin() {
    const { isSignedIn } = useUser();
    const api = useApi();

    useEffect(() => {
        if (isSignedIn) {
            // Idempotent — safe to call every login
            api.post('/provision').catch(console.error);
        }
    }, [isSignedIn]);

    return null;
}
```

### 4.6 Add environment variables for frontend

Create `frontend/.env.production`:
```
VITE_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx
VITE_API_URL=https://your-backend.railway.app
```

Create `frontend/.env.development` (already works locally):
```
VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
VITE_API_URL=http://localhost:8000
```

### 4.7 Gmail onboarding wizard

After first login, the app checks `/gmail-setup/status`. If
`configured: false`, redirect the user to `/setup` before they can use
the dashboard. This is a 4-step wizard — each step has a direct link or
action so the user never has to search for anything.

**Route:** add `/setup` to `App.jsx` (accessible only when signed in,
redirect here instead of `/` when `configured: false`):

```jsx
<Route path="/setup" element={<GmailSetup />} />
```

**`frontend/src/pages/GmailSetup.jsx` — wizard structure:**

```jsx
// Step 1 — Enable IMAP
// Show a screenshot of Gmail Settings > See all settings > Forwarding and POP/IMAP
// Button: "Open Gmail Settings" → window.open("https://mail.google.com/mail/u/0/#settings/fwdandpop")
// Instruction: Toggle "Enable IMAP" → Save Changes

// Step 2 — Create the 3 labels
// For each label name, show a "Create label" button that deep-links:
// window.open(`https://mail.google.com/mail/u/0/#create-label?name=${label}`)
// Labels needed: sync-expense-tracker, expenses, non-transaction
// Explain purpose: source (unprocessed), done (processed), ignored

// Step 3 — Generate App Password
// Button: "Open Google App Passwords" → window.open("https://myaccount.google.com/apppasswords")
// Instructions with screenshot:
//   1. Select app: Mail
//   2. Select device: Other → type "Expense Tracker"
//   3. Copy the 16-character password shown

// Step 4 — Connect
// Two inputs: Gmail address + App Password
// On submit: POST /gmail-setup/save
//   - If connection fails → show error inline ("Login failed — check password")
//   - If connection succeeds → show which labels were found vs missing
//     - Missing labels: show warning with direct create link (loop back to Step 2)
//     - All labels found: enable "Finish setup" button
// On finish: POST /gmail-setup/mark-ready → redirect to "/"
```

**Progress persistence:** store completed steps in `localStorage` so
refreshing the page doesn't reset the wizard.

**Skip option:** users who already set up labels manually can jump
straight to Step 4.

---

## Phase 5 — Railway Deployment (Backend)

1. Push the updated backend code to GitHub
2. In Railway: **New Project → Deploy from GitHub repo**
3. Select the repo, set the **root directory** to `backend/`
4. Set the **start command** to:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add the following **environment variables** in Railway's dashboard:

| Variable | Value |
|---|---|
| `DB_USER` | from Neon connection string |
| `DB_PASS` | from Neon connection string |
| `PG_HOST` | from Neon connection string |
| `DB_NAME` | from Neon connection string |
| `CLERK_JWKS_URL` | from Clerk dashboard → API Keys → JWKS URL |
| `ENCRYPTION_KEY` | generate a random 32-byte key for Gmail password encryption |

6. Railway auto-assigns a public URL (e.g. `https://expense-tracker.railway.app`)
7. Copy that URL and update `allow_origins` in `main.py` and `VITE_API_URL` in Vercel

---

## Phase 6 — Vercel Deployment (Frontend)

1. Push frontend code to GitHub
2. In Vercel: **New Project → Import Git Repository**
3. Set **framework preset** to Vite
4. Set **root directory** to `frontend/`
5. Add the following **environment variables** in Vercel's dashboard:

| Variable | Value |
|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | from Clerk dashboard |
| `VITE_API_URL` | Railway backend URL from Phase 5 |

6. Click **Deploy** — Vercel builds and hosts the static frontend
7. Vercel assigns a URL (e.g. `https://expense-tracker.vercel.app`)
8. Copy that URL and update `allow_origins` in `main.py`, then redeploy Railway

---

## Phase 7 — Clerk Configuration

1. In the Clerk dashboard, go to **Domains**
2. Add your Vercel URL as an allowed domain
3. Go to **API Keys**, copy:
   - **Publishable key** → Vercel env var
   - **JWKS URL** → Railway env var
4. Under **User & Authentication**, enable Email and Google as sign-in methods

---

## Phase 8 — Smoke Test Checklist

Run these checks after all three services are deployed:

- [ ] Opening the Vercel URL redirects to Clerk's sign-in page
- [ ] Signing up with a new email creates an account
- [ ] After sign-in, `/provision` is called and returns `{"status": "ready"}`
- [ ] Dashboard loads without errors (empty state is fine)
- [ ] Adding a transaction saves and appears in the list
- [ ] Logging in from a different browser/account shows a separate empty dashboard
- [ ] Signing out redirects back to the sign-in page

---

## Local Development After These Changes

To run locally with auth enabled, use Clerk's test keys:

```bash
# frontend/.env.development
VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
VITE_API_URL=http://localhost:8000

# backend/.env
DB_USER=...
DB_PASS=...
PG_HOST=...        # can point to Neon even locally
DB_NAME=...
CLERK_JWKS_URL=https://your-app.clerk.accounts.dev/.well-known/jwks.json
```

Start backend: `uvicorn app.main:app --reload` (from `backend/`)
Start frontend: `npm run dev` (from `frontend/`)

---

## Cost Summary

| Service | Free Tier | When You'd Pay |
|---|---|---|
| Vercel | Unlimited for personal projects | Never (personal use) |
| Railway | $5/month free credit | If compute exceeds ~500 hours/month |
| Neon | 0.5 GB, ~500–1000 users | $19/month at scale |
| Clerk | 10,000 MAU free | $25/month beyond 10k users |
| **Total** | **~$0/month** | **~$44/month at real scale** |

---

## Open Questions / Future Work

- **OAuth2 migration**: The App Password approach works well for a small user
  base. If the app grows beyond ~50 users, switching to Google OAuth2 + Gmail
  API removes all manual setup steps (one click instead of 4 manual steps).
  This requires a Google Cloud project and app verification (~4–6 weeks).
  Not worth it until scale demands it.
- **Email backfill UX**: After setup, users with months of past bank emails
  need to move them into `sync-expense-tracker`. A future improvement could
  auto-suggest a Gmail filter/search query to bulk-select and relabel old
  emails (e.g. `from:(alerts@hdfcbank.com OR noreply@icicibank.com)`).
- **Mobile (PWA)**: After the web deployment is stable, add a `manifest.json`
  and service worker for installable mobile experience with no extra cost.
- **Capacitor (native app)**: If App Store presence is needed, wrap the
  existing React app with Capacitor — no frontend rewrite required.
