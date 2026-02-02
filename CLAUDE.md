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
| Business logic | `backend/app/services/*.py` | Analytics, rules, duplicates, subscriptions, trends, chatbot |
| Frontend entry | `frontend/src/App.jsx` | React Router setup |
| API client | `frontend/src/api/axios.js` | Base URL: localhost:8000 |
| Trends engine | `backend/app/services/trends.py` | Spending pattern analysis |
| Chatbot service | `backend/app/services/chatbot.py` | LLM-powered financial assistant |
| Chat widget | `frontend/src/components/ChatBot.jsx` | Floating chat UI |

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
- `GEMINI_API_KEY` - For chatbot LLM (free at https://aistudio.google.com)

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
| `/trends` | Spending trends | Monthly/category analysis, affordability simulation |
| `/chatbot` | Financial assistant | LLM-powered Q&A about finances |

## Spending Trends Engine

The trends engine (`backend/app/services/trends.py`) provides spending pattern analysis:

| Feature | Description |
|---------|-------------|
| Monthly aggregations | Spending totals by month |
| Category trends | Track if categories are increasing/decreasing/stable |
| Seasonal patterns | Identify high-spend months (e.g., December) |
| Day-of-week analysis | Average spending by weekday |
| Recurring detection | Identify regular merchants beyond subscriptions |
| Affordability calculator | Simulate budget impact of new expenses |

**Endpoints:**
- `GET /trends/overview` - Full trends analysis
- `GET /trends/category/{name}` - Category-specific trends
- `POST /trends/simulate-affordability` - Budget impact simulation

## Chatbot (Financial Assistant)

Privacy-first LLM chatbot (`backend/app/services/chatbot.py`) with local computation:

**Architecture:**
```
User Question → Intent Detection (LOCAL) → Handler
                                              ↓
                    ┌─────────────────────────┴─────────────────────────┐
                    ↓                                                   ↓
             LOCAL COMPUTE                                        LLM API (Gemini)
             - Budget calculations                                - Product price lookup
             - Trend analysis                                     - Response formatting
             - Affordability check                                (No financial data sent)
```

**Supported Queries:**
- Budget status: "What's my remaining budget?"
- Category spending: "How much do I spend on food?"
- Trends: "What are my spending trends?"
- Affordability: "Can I buy an iPhone 15 in EMI?"
- Savings: "Where can I cut expenses?"

**Rate Limits (Gemini Free Tier):**
- 15 requests/minute
- 1,500 requests/day

**Endpoints:**
- `POST /chatbot/ask` - Send message, get response
- `GET /chatbot/rate-limit` - Check remaining requests

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
- Chatbot uses local intent detection - LLM only for product price lookups
- Burn rate status: `Over Budget` → `High Burn` → `Caution` → `On Track`
- Settings validation: `salary_day` (1-31), `budget_value` (>= 0)

## Troubleshooting

### Chatbot not responding to queries

If the chatbot returns generic messages or fails on affordability queries:

1. **Check GEMINI_API_KEY**: Ensure `backend/.env` contains `GEMINI_API_KEY=your_key_here`
2. **Restart server**: The `.env` is loaded at module import time - restart uvicorn after adding the key
3. **Check rate limits**: Gemini free tier has 15 req/min and 1500 req/day limits

The chatbot service (`backend/app/services/chatbot.py`) loads `.env` from `backend/.env` using a resolved path, so it works regardless of the current working directory when starting uvicorn.
