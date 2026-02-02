# Expense Tracker

Personal expense tracking application with automated email-to-transaction ingestion.

## Tech Stack

**Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL + Pydantic
**Frontend**: React 19 + Vite + Tailwind CSS + Recharts
**ETL**: Python IMAP client with BeautifulSoup for email parsing

## Project Structure

```
expense-tracker/
├── backend/app/           # FastAPI application
│   ├── main.py            # App entry, CORS, router registration
│   ├── database.py        # Async SQLAlchemy engine & session
│   ├── models.py          # ORM models (Transaction, Category, Rule, etc.)
│   ├── routers/           # API endpoints (transactions, dashboard, rules, etc.)
│   ├── services/          # Business logic layer
│   └── schemas/           # Pydantic request/response models
├── frontend/src/          # React SPA
│   ├── api/axios.js       # Configured Axios instance
│   ├── components/        # Reusable UI components
│   ├── pages/             # Route pages (Dashboard, Transactions, etc.)
│   └── utils/             # Helper functions
└── Etl/                   # Email ingestion pipeline
    ├── main.py            # Pipeline orchestration
    ├── parsers.py         # Email content extraction
    └── email_service.py   # IMAP operations
```

## Key Files

| Purpose | File | Notes |
|---------|------|-------|
| Database models | `backend/app/models.py` | 6 tables: Transaction, Category, TransactionRule, etc. |
| DB connection | `backend/app/database.py` | Async PostgreSQL with `get_db()` dependency |
| API routes | `backend/app/routers/*.py` | Each resource has dedicated router |
| Business logic | `backend/app/services/*.py` | Analytics, rules, duplicates, subscriptions |
| Frontend entry | `frontend/src/App.jsx` | React Router setup |
| API client | `frontend/src/api/axios.js` | Base URL: localhost:8000 |

## Commands

### Backend
```bash
# Start dev server (from project root)
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Install dependencies
pip install -r backend/requirements.txt
```

### Frontend
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Start dev server (localhost:5173)
npm run build        # Production build
npm run lint         # Run ESLint
```

### ETL Pipeline
```bash
pip install -r Etl/requirements.txt
python Etl/main.py   # Run email sync
```

## Environment Variables

Create `.env` files (git-ignored) with:

**Backend** (`backend/.env`):
- `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME`

**ETL** (`Etl/.env`):
- `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_HOST`
- Database credentials (same as backend)

## Database Schema

Core relationships:
- `Transaction` → `Category` (many-to-one via `category_id`)
- `TransactionRule` → `Category` (rules auto-assign categories)
- `RecurringExpense` → `Transaction` (subscription tracking)
- `StagingTransaction` (unmatched emails pending review)

Tables defined in `backend/app/models.py:1-77`

## API Endpoints

| Prefix | Resource | Key Operations |
|--------|----------|----------------|
| `/transactions` | Transactions | CRUD, filtering, search, pagination |
| `/dashboard` | Analytics | Stats, trends, cycle calculations |
| `/categories` | Categories | List, create |
| `/rules` | Auto-categorization | Create rules, apply historically |
| `/staging` | Pending transactions | Review, approve, dismiss |
| `/subscription` | Recurring expenses | Track subscriptions |

## Adding New Features or Fixing Bugs

**Important**: When you work on a new feature or bug, create a git branch first. Then work on changes in that branch for the remainder of the session.

## Additional Documentation

Check these files for detailed patterns and conventions:

| Topic | File |
|-------|------|
| Architecture & Design Patterns | `.claude/docs/architectural_patterns.md` |

## Quick Reference

- All backend services are async - use `await` with database operations
- Pydantic schemas use `ConfigDict(from_attributes=True)` for ORM compatibility
- Frontend state management uses React hooks (useState, useEffect)
- CORS allows localhost:5173 (Vite) and localhost:3000
- Transactions support salary cycle-based filtering via `offset` parameter
