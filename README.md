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

## Quick Start (Recommended)

The easiest way to get running is the **Setup Wizard** — a browser-based app that handles everything automatically.

### Prerequisites (install these first)

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.10+ | [python.org/downloads](https://www.python.org/downloads/) |
| Node.js | 18+ LTS | [nodejs.org/en/download](https://nodejs.org/en/download) |
| PostgreSQL | 14+ | [postgresql.org/download](https://www.postgresql.org/download/) |

### First-Time Setup

**Mac / Linux:**
```bash
# Make the launcher executable (one-time)
chmod +x "Start Setup.command"

# Then double-click "Start Setup.command" in Finder
# — OR run from terminal:
python3 setup/setup.py
```

**Windows:**
Double-click **`Start Setup.bat`**

The setup wizard will open in your browser and guide you through:
1. Checking software prerequisites
2. Setting up the PostgreSQL database
3. Connecting your Gmail account (via App Password)
4. Creating the required Gmail labels
5. Configuring your AI assistant (Gemini or Groq — both free)
6. Installing all dependencies automatically
7. Launching the app

### Launching After First Setup

**Mac / Linux:** Double-click **`Start App.command`** (or run `python3 setup/setup.py --launch`)

**Windows:** Double-click **`Start App.bat`**

---

## Manual Setup (Advanced)

If you prefer to set up manually, here are the steps:

### 1. Clone the repository

```bash
git clone <repo-url>
cd expense-tracker
```

### 2. Database Setup

```sql
CREATE USER tracker_user WITH PASSWORD 'your_password';
CREATE DATABASE expense_tracker OWNER tracker_user;
```

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
DB_NAME=expense_tracker
DB_USER=tracker_user
DB_PASS=your_password

# LLM (choose one)
LLM_BACKEND=GEMINI
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
DB_NAME=expense_tracker
DB_USER=tracker_user
DB_PASS=your_password
DATABASE_URL=postgresql://tracker_user:your_password@localhost/expense_tracker
```

Run the pipeline:

```bash
python main.py
```

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
3. Create Gmail labels: `sync-expense-tracker`, `expenses`, `non-transaction`
4. Set up a Gmail filter to route HDFC bank emails to `sync-expense-tracker`
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
