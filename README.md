# Expense Tracker

A full-stack personal finance tracker that automatically extracts transactions from bank emails (Gmail), categorizes them, and provides AI-powered spending insights through a multi-agent chatbot.

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | React 19, Vite, React Router, Tailwind CSS, Recharts |
| Backend | FastAPI, SQLAlchemy (async), Pydantic |
| Database | PostgreSQL (asyncpg) |
| ETL | Python, IMAP (Gmail), BeautifulSoup |
| AI/LLM | Google Gemini API |

## Features

- **Email-based Transaction Ingestion** — Parses bank notification emails from Gmail via IMAP, extracts amount, merchant, date, and payment mode (UPI/Card/Netbanking)
- **Dashboard Analytics** — Financial health score, monthly spending breakdown, budget tracking, category-wise analysis
- **Multi-Agent AI Chatbot** — Orchestrated agents for budget analysis, trend detection, forecasting, affordability checks, and goal tracking
- **Smart Search** — Natural language transaction search (e.g., "food expenses over 500 last week")
- **Automation Rules** — Pattern-based merchant name standardization and auto-categorization
- **Spending Trends** — Monthly trends, day-of-week patterns, seasonal analysis, recurring merchant detection
- **Spending Goals** — Set and track monthly spending caps per category
- **Recurring Expenses** — Subscription and recurring payment tracking
- **Duplicate Detection** — Hard/soft duplicate detection with resolution workflow
- **Needs Review Queue** — Non-transaction emails staged for manual review

## Project Structure

```
expense-tracker/
├── frontend/          # React + Vite SPA
│   ├── src/
│   │   ├── api/       # Axios HTTP client
│   │   ├── components/# UI components (Sidebar, EmbeddedChat, Layout)
│   │   ├── pages/     # Dashboard, Transactions, Duplicates, NeedsReview, Profile
│   │   ├── hooks/     # useFocusTrap, useSmartSearch
│   │   ├── contexts/  # React Context providers
│   │   └── utils/     # Utility functions
│   └── package.json
│
├── backend/           # FastAPI REST API
│   ├── app/
│   │   ├── routers/   # API endpoints (10 routers)
│   │   ├── services/  # Business logic + multi-agent system
│   │   │   └── agents/# Orchestrator, compute agents (budget, trends, forecast, affordability, goals)
│   │   ├── schemas/   # Pydantic request/response models
│   │   ├── models.py  # SQLAlchemy ORM models
│   │   ├── database.py# Async PostgreSQL connection
│   │   └── main.py    # FastAPI app entry point
│   └── requirements.txt
│
└── Etl/               # Email extraction pipeline
    ├── main.py        # Pipeline orchestrator
    ├── email_service.py # Gmail IMAP integration
    ├── parsers.py     # Transaction extraction from email HTML
    ├── database.py    # DB bootstrap & operations
    ├── config.py      # Environment configuration
    └── requirements.txt
```

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **PostgreSQL 14+**
- **Gmail account** with an [App Password](https://support.google.com/accounts/answer/185833) enabled
- **Groq API key** — Get one at [console.groq.com](https://console.groq.com)
- **Google Gemini API key** — Get one at [aistudio.google.com](https://aistudio.google.com/apikey)

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd expense-tracker
```

### 2. Database Setup

Create a PostgreSQL database and user:

```sql
CREATE USER tracker_user WITH PASSWORD 'your_password';
CREATE DATABASE expense_tracker_test OWNER tracker_user;
```

Alternatively, the ETL pipeline's `database.py` can bootstrap the database and tables automatically on first run (requires PostgreSQL admin credentials in `.env`).

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
# Database
PG_ADMIN_USER=postgres
PG_ADMIN_PASS=your_admin_password
PG_HOST=localhost
DB_NAME=expense_tracker_test
DB_USER=tracker_user
DB_PASS=your_password

# LLM
GEMINI_API_KEY=your_gemini_api_key

# Email (IMAP)
IMAP_SERVER=imap.gmail.com
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_gmail_app_password
MAIL_SERVER=imap.gmail.com
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

The API will be available at **http://localhost:8000**. Interactive docs at http://localhost:8000/docs.

### 4. ETL Pipeline

```bash
cd Etl
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `Etl/.env`:

```env
IMAP_SERVER=imap.gmail.com
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_gmail_app_password

PG_ADMIN_USER=postgres
PG_ADMIN_PASS=your_admin_password
PG_HOST=localhost
DB_NAME=expense_tracker_test
DB_USER=tracker_user
DB_PASS=your_password
DATABASE_URL=postgresql://tracker_user:your_password@localhost/expense_tracker_test
```

Run the pipeline:

```bash
python main.py
```

This connects to Gmail via IMAP, reads emails from the `sync-expense-tracker` folder, extracts transactions, and loads them into PostgreSQL. Processed emails are moved to an `expenses` folder; non-transaction emails go to `non-transaction`.

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at **http://localhost:5173**.

## Gmail IMAP Setup

1. Enable IMAP in your Gmail settings (Settings > See all settings > Forwarding and POP/IMAP)
2. Generate an [App Password](https://support.google.com/accounts/answer/185833) (requires 2FA enabled)
3. Create a Gmail label/folder named `sync-expense-tracker`
4. Set up a Gmail filter to route bank notification emails to this folder
5. Use the app password in your `.env` files

## API Endpoints

The backend exposes the following router groups:

| Router | Path | Purpose |
|--------|------|---------|
| Transactions | `/transactions` | CRUD operations, search, filtering |
| Dashboard | `/dashboard` | Analytics, financial health, spending summary |
| Categories | `/categories` | Category management |
| Staging | `/staging` | Unmatched email review queue |
| Rules | `/rules` | Merchant name/category automation rules |
| Subscriptions | `/subscription` | Recurring expense tracking |
| Trends | `/trends` | Spending trends and pattern analysis |
| Chatbot | `/chatbot` | AI-powered conversational analysis |
| Sync | `/sync` | Trigger email sync from the app |
| Goals | `/goals` | Monthly spending goal management |

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `PG_ADMIN_USER` | Yes | PostgreSQL admin username |
| `PG_ADMIN_PASS` | Yes | PostgreSQL admin password |
| `PG_HOST` | Yes | PostgreSQL host (default: `localhost`) |
| `DB_NAME` | Yes | Database name |
| `DB_USER` | Yes | Application database user |
| `DB_PASS` | Yes | Application database password |
| `LLM_BACKEND` | Yes | LLM provider (`GROQ` or `GEMINI`) |
| `GROQ_API_KEY` | Yes | Groq API key for chatbot |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `IMAP_SERVER` | Yes | IMAP server (default: `imap.gmail.com`) |
| `IMAP_USER` | Yes | Gmail address |
| `IMAP_PASSWORD` | Yes | Gmail app password |

## Running All Services

Open three terminals:

```bash
# Terminal 1 — Backend API
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend && npm run dev

# Terminal 3 — ETL (run once or as needed)
cd Etl && source venv/bin/activate && python main.py
```
