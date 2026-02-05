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
│   │   └── ui/            # Design system components (Toast, Skeleton, etc.)
│   ├── contexts/          # React context providers
│   ├── hooks/             # Custom React hooks
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
| Business logic | `backend/app/services/*.py` | Analytics, rules, duplicates, subscriptions, trends, chatbot, smart_search |
| Frontend entry | `frontend/src/App.jsx` | React Router setup |
| API client | `frontend/src/api/axios.js` | Base URL: localhost:8000 |
| Trends engine | `backend/app/services/trends.py` | Spending pattern analysis |
| Agent system | `backend/app/services/agents/` | Multi-agent chatbot system (orchestrator, parser, compute agents) |
| Chatbot service | `backend/app/services/chatbot.py` | Legacy chatbot service (fallback only) |
| Chatbot compute | `backend/app/services/chatbot_compute.py` | Modular computation functions for chatbot |
| Chat widget | `frontend/src/components/ChatBot.jsx` | Floating chat UI with session management |
| Smart search | `backend/app/services/smart_search.py` | AI-powered natural language transaction search |
| Search summary | `frontend/src/components/ui/SearchSummary.jsx` | Debit/credit totals display |

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
| `/sync` | Email sync | Trigger ETL pipeline from dashboard |

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

Privacy-first LLM chatbot with conversational AI, session memory, and predictive capabilities.

**Design Principle:** "The LLM is the Brain, but the Backend is the Hands"
- LLM handles planning (query parsing) and natural language (response formatting)
- Python agents execute secure local financial computations

**Architecture (Multi-Agent System):**
```
User Query + Session ID
        ↓
┌─────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                          │
│  - Manages session (30min TTL)                              │
│  - Creates TaskDAG via ParserAgent                          │
│  - Executes tasks (parallel when independent)               │
│  - Formats response via AggregatorAgent                     │
└────────────────────────────┬────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ↓                   ↓                   ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  PARSER AGENT   │  │  COMPUTE AGENTS │  │ AGGREGATOR AGENT│
│  (LLM-powered)  │  │  (Python only)  │  │  (LLM-powered)  │
│                 │  │                 │  │                 │
│ - Parse query   │  │ - BudgetAgent   │  │ - Combine data  │
│ - Create DAG    │  │ - TrendsAgent   │  │ - Format prose  │
│ - Set deps      │  │ - ForecastAgent │  │ - Handle errors │
└─────────────────┘  │ - AffordAgent   │  └─────────────────┘
                     └─────────────────┘
```

**Fallback:** If LLM unavailable or rate limited, falls back to regex-based intent detection (legacy `chatbot.py`).

**Session Memory:**
- Sessions stored in-memory with 30-minute TTL
- Max 1000 concurrent sessions
- Last 10 messages stored per session
- Enables follow-up queries: "What about last month?" (uses previous category)
- Frontend stores session_id in sessionStorage

**Supported Queries:**

*Simple queries:*
- Budget status: "What's my remaining budget?"
- Category spending: "How much do I spend on food?"
- Trends: "What are my spending trends?"
- Affordability: "Can I buy an iPhone 15 in EMI?"
- Savings: "Where can I cut expenses?"

*Time-range queries:*
- "How much have I spent on fuel in the past 3 months?"
- "What's my food spending this month?"
- "Spending on entertainment last week"

*Predictive queries:*
- "Can I save ₹50,000 in 6 months?"
- "Will I stay under budget this month?"
- "What's my average monthly food spending?"
- "Is my spending increasing or decreasing?"

*Complex/hypothetical queries:*
- "If I reduce food spending by 10k per month, can I afford Japan flights in 6 months?"
- "What if I cut my entertainment budget in half for 3 months?"

*Follow-up queries (requires session):*
- "What about last month?" (uses previous query context)
- "And for entertainment?" (switches category, keeps time range)

**Operation Types:**
| Type | Description | Params |
|------|-------------|--------|
| `budget_status` | Current budget, spending, remaining | None |
| `category_spend` | Spending for a category | `category_name` |
| `trends_overview` | Spending trends analysis | None |
| `affordability_check` | Can user afford X (auto-fetches price) | `product_name`, `monthly_cost` |
| `savings_advice` | Savings suggestions | None |
| `custom_scenario` | Project future savings with adjustments | `adjustments`, `months` |
| `time_range_spend` | Spending for specific period | `category_name`, `months_back`, `relative` |
| `average_spending` | Average monthly spending | `category_name`, `months_back` |
| `spending_velocity` | Rate of spending change | `window_days` |
| `future_projection` | Project future spending/savings | `months_forward`, `adjustments` |
| `goal_planning` | Plan to reach savings goal | `target_amount`, `target_months`, `goal_name` |
| `budget_forecast` | Will I stay under budget? | `days_forward` |
| `clarify` | Ask follow-up question | `question` |

**Modular Compute Functions (`chatbot_compute.py`):**
| Function | Description |
|----------|-------------|
| `get_avg_spending_by_category()` | Average monthly spend per category |
| `get_avg_transaction_amount()` | Average transaction value with filters |
| `get_spending_velocity()` | Rate of spending change (current vs previous window) |
| `get_category_breakdown_for_period()` | Category breakdown for date range |
| `calculate_time_range_spend()` | Flexible time range spending totals |
| `project_future_spending()` | Multi-month projection with adjustments |
| `calculate_goal_plan()` | Plan to reach savings goal with suggestions |
| `forecast_budget_status()` | Forecast budget status for end of cycle |

**Historical Averaging (`_get_historical_averages`):**
For predictive queries, the system uses 3-month historical data:
- `avg_monthly_budget` - Average budget (fixed or % of income)
- `avg_monthly_spend` - Average total spending
- `avg_monthly_surplus` - Budget minus spend (savings capacity)
- `avg_category_spend` - Average spend per category

**Chained Operations:** For complex queries, operations chain together with shared context:
```
custom_scenario → accumulated_context → affordability_check
     ↓                                        ↓
Calculate projected savings       Compare savings vs product price
```

**Example Flow:** "Can I afford Japan flights if I reduce food by 10k for 6 months?"
1. `custom_scenario`: Uses historical avg_food_spend, calculates new surplus, projects 6-month savings
2. `affordability_check`: Gets flight price from LLM, compares against projected savings
3. Returns: "Yes, by saving ₹10k/month on food, you'll have ₹X after 6 months, which covers the ₹Y flight cost."

**Rate Limits (Gemini Free Tier):**
- 15 requests/minute
- 1,500 requests/day
- Conversational flow uses ~2 LLM calls per message (analyze + format)

**Key Files:**
| File | Purpose |
|------|---------|
| `backend/app/services/agents/` | Multi-agent system directory |
| `backend/app/services/agents/__init__.py` | Main exports: `process_chat_message`, `get_rate_limit_status` |
| `backend/app/services/agents/orchestrator.py` | DAG execution, topological sort, parallel processing |
| `backend/app/services/agents/parser.py` | LLM query parsing → TaskDAG |
| `backend/app/services/agents/aggregator.py` | LLM response formatting |
| `backend/app/services/agents/memory.py` | SessionManager, ConversationSession |
| `backend/app/services/agents/llm.py` | Gemini API client, rate limiting |
| `backend/app/services/agents/compute/` | Compute agents directory |
| `backend/app/services/agents/compute/budget.py` | BudgetAgent: budget_status, category_spend, budget_forecast |
| `backend/app/services/agents/compute/trends.py` | TrendsAgent: trends_overview, savings_advice, spending_velocity |
| `backend/app/services/agents/compute/forecast.py` | ForecastAgent: time_range_spend, average_spending, custom_scenario, goal_planning |
| `backend/app/services/agents/compute/affordability.py` | AffordabilityAgent: affordability_check (with LLM price lookup) |
| `backend/app/schemas/agents/task.py` | Task, TaskDAG, TaskResult, TaskStatus, TaskType |
| `backend/app/schemas/agents/trace.py` | ExecutionTrace, TraceEvent (debugging/observability) |
| `backend/app/services/chatbot.py` | Legacy monolithic service (fallback only) |
| `backend/app/services/chatbot_compute.py` | Shared computation functions used by agents |
| `frontend/src/components/ChatBot.jsx` | Chat widget with session support |

**Agent-to-TaskType Mapping:**
| Agent | Task Types |
|-------|------------|
| BudgetAgent | `budget_status`, `category_spend`, `budget_forecast` |
| TrendsAgent | `trends_overview`, `savings_advice`, `spending_velocity` |
| ForecastAgent | `time_range_spend`, `average_spending`, `future_projection`, `custom_scenario`, `goal_planning` |
| AffordabilityAgent | `affordability_check` |

**Parallel Execution:**
The orchestrator uses topological sort to identify independent tasks:
```
Level 0: [Task A, Task B]  → Run in parallel
Level 1: [Task C depends on A]  → Run after Level 0 completes
```
For "If I reduce food by 10k, can I afford Japan flights?":
- Level 0: `custom_scenario` (calculate projected savings)
- Level 1: `affordability_check` (uses savings from Level 0)

**API:**
- `POST /chatbot/ask` - Send message with optional `session_id`, get response with `session_id`
- `GET /chatbot/rate-limit` - Check remaining requests

**Request/Response:**
```json
// Request
{
  "message": "How much have I spent on food?",
  "session_id": "optional-session-id"
}

// Response
{
  "response": "You've spent ₹12,500 on food this cycle...",
  "intent": "conversational",
  "requires_llm": true,
  "rate_limit": {"daily_remaining": 1480, "minute_remaining": 13},
  "session_id": "uuid-for-follow-up-queries"
}
```

## Smart Search & Transaction Summary

The Transactions page includes AI-powered natural language search with transaction summary display.

### Smart Search (`backend/app/services/smart_search.py`)

**Architecture:**
```
User Query → detect_search_type() → 'smart' or 'fuzzy'
                                           ↓
            ┌──────────────────────────────┴──────────────────────────────┐
            ↓                                                              ↓
      SMART (AI)                                                      FUZZY (Simple)
      - Call Gemini API                                               - Text match on
      - Parse natural language                                          merchant/category
      - Extract filters                                               - No LLM needed
            ↓
      SmartSearchFilters
      (categories, amounts, dates, payment_type, merchant_pattern)
```

**Supported Queries:**
- `"food expenses over 500 last week"` → Filters: category=Food, amount_min=500, date_from=7 days ago
- `"swiggy transactions this month"` → Filters: merchant_pattern=swiggy, date_from=1st of month
- `"income last month"` → Filters: payment_type=CREDIT, date_from=30 days ago

**Endpoints:**
- `GET /transactions` - Supports `category_ids`, `amount_min`, `amount_max`, `merchant_pattern` params
- `POST /transactions/smart-search` - Natural language search with parsed filter response

**Rate Limits:** Shares Gemini quota with chatbot (15/min, 1500/day)

### Transaction Summary Display

The SearchSummary component shows aggregated totals for filtered transactions:

| Field | Description | Color |
|-------|-------------|-------|
| Spent | Sum of DEBIT transactions | Red |
| Received | Sum of CREDIT transactions | Green |
| Net Gain/Spend | credit_sum - debit_sum | Green if positive, Red if negative |

### Category Multiselect Filter

Click the "Category" table header to open a dropdown with:
- Checkboxes for each category
- Selected count badge
- Clear all button

### Key Files

| Purpose | File |
|---------|------|
| Smart search service | `backend/app/services/smart_search.py` |
| Smart search schemas | `backend/app/schemas/smart_search.py` |
| Search input component | `frontend/src/components/ui/SmartSearchInput.jsx` |
| Summary display | `frontend/src/components/ui/SearchSummary.jsx` |
| Category filter | `frontend/src/components/ui/CategoryMultiselect.jsx` |
| Smart search hook | `frontend/src/hooks/useSmartSearch.js` |
| Toast notifications | `frontend/src/components/ui/Toast.jsx` |
| Toast context | `frontend/src/contexts/ToastContext.jsx` |
| Skeleton loaders | `frontend/src/components/ui/Skeleton.jsx` |
| Card skeletons | `frontend/src/components/ui/CardSkeleton.jsx` |
| Table skeletons | `frontend/src/components/ui/TableSkeleton.jsx` |
| Focus trap hook | `frontend/src/hooks/useFocusTrap.js` |

## UI/UX Design System

### Color Scheme

| Purpose | Color | Tailwind Class |
|---------|-------|----------------|
| Primary Action | Teal | `bg-teal-600 hover:bg-teal-500` |
| Credit/Positive | Emerald | `text-emerald-400` |
| Debit/Negative | Red | `text-red-400` |
| AI Features | Purple | `text-purple-400` |
| Neutral Text | Slate | `text-slate-300` (body), `text-slate-400` (labels) |
| Backgrounds | Dark | `bg-[#0a0a0a]` (main), `bg-[#161616]` (cards) |

### Reusable UI Components

| Component | File | Purpose |
|-----------|------|---------|
| Toast | `frontend/src/components/ui/Toast.jsx` | Notification system |
| ToastContext | `frontend/src/contexts/ToastContext.jsx` | Toast state management |
| Skeleton | `frontend/src/components/ui/Skeleton.jsx` | Loading state primitives |
| TableSkeleton | `frontend/src/components/ui/TableSkeleton.jsx` | Table loading state |
| CardSkeleton | `frontend/src/components/ui/CardSkeleton.jsx` | Card/dashboard loading states |

### Toast Notifications

Use the toast context instead of `alert()`:

```jsx
import { useToast } from '../contexts/ToastContext';

const MyComponent = () => {
    const toast = useToast();

    const handleSave = async () => {
        try {
            await api.post('/save');
            toast.success('Saved successfully!');
        } catch (e) {
            toast.error('Failed to save');
        }
    };
};
```

**Available methods:**
- `toast.success(message)` - Green success notification
- `toast.error(message)` - Red error notification
- `toast.warning(message)` - Amber warning notification
- `toast.info(message)` - Blue informational notification

### Skeleton Loaders

Replace text loading states with skeletons:

```jsx
import { DashboardSkeleton } from '../components/ui/CardSkeleton';
import TableSkeleton from '../components/ui/TableSkeleton';

// For dashboard
if (loading) return <DashboardSkeleton />;

// For tables
if (loading) return <TableSkeleton rows={8} />;
```

**Available skeletons:**
- `DashboardSkeleton` - Full dashboard layout
- `ProfileSkeleton` - Profile/settings page
- `InboxSkeleton` - Needs Review page
- `DuplicatesSkeleton` - Duplicates page
- `TableSkeleton` - Generic table rows

### Mobile Responsiveness

- Sidebar collapses to hamburger menu at `<768px` (lg breakpoint)
- Tables wrapped in `overflow-x-auto` with `min-w-[800px]` for horizontal scroll
- ChatBot supports touch drag on mobile devices
- Chat window uses responsive width: `w-[calc(100vw-2rem)] max-w-96 sm:w-96`
- Modals use `max-w-lg w-full mx-4` for mobile padding

### Accessibility Standards

- All modals trap focus using `useFocusTrap` hook and close with Escape key
- Chat messages container has `aria-live="polite"` for screen readers
- All inputs use `focus:border-teal-500` consistently
- Icon-only buttons have `aria-label` attributes
- Modals have `role="dialog"`, `aria-modal="true"`, and `aria-labelledby`
- No array index keys in React lists (use unique IDs)

### Focus Trap Usage

For modals that need keyboard accessibility:

```jsx
import useFocusTrap from '../hooks/useFocusTrap';

const MyModal = ({ isOpen, onClose }) => {
    const modalRef = useFocusTrap(isOpen, onClose);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 ...">
            <div
                ref={modalRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="modal-title"
            >
                <h2 id="modal-title">Modal Title</h2>
                {/* Modal content */}
            </div>
        </div>
    );
};
```

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

### Affordability check shows wrong budget

The affordability calculator supports two budget types:

- **PERCENTAGE**: Budget is calculated as a percentage of average monthly salary from income transactions
- **FIXED**: Budget uses the `monthly_budget` or `budget_value` directly as an absolute amount

**How PERCENTAGE budget works:**
1. Fetches CREDIT transactions from categories listed in `income_categories` (last 12 months)
2. Groups by month and calculates average monthly income
3. Applies the `budget_value` percentage (e.g., 40% of ₹100,000 = ₹40,000)

**Common issues:**
- **Budget shows ₹0 or error**: No income transactions found in configured income categories. Ensure salary/income transactions exist and are categorized correctly.
- **Wrong percentage applied**: Check that `budget_type` is set to `"PERCENTAGE"` in dashboard settings, not `"FIXED"`.
- **Incorrect income categories**: Verify `income_categories` in settings includes the category name for your salary transactions (e.g., "Salary", "Income").

### ETL pipeline not applying rules

If auto-categorization rules aren't being applied during email sync:

1. **Table name mismatch**: The ETL was querying `category_rules` instead of `transaction_rules`. This has been fixed.
2. **Verify rules exist**: Check that rules are created in the Rules page before running sync.

### Sync fails with "column 'keyword' does not exist"

**Fixed:** The ETL rule-matching query in `Etl/database.py:51` was using `keyword` but the actual column in `transaction_rules` is `pattern`. The query has been updated to use the correct column name.

### Chatbot affordability returns bullet-points instead of conversational response

**Fixed:** The `handle_affordability` function in `backend/app/services/chatbot.py` was returning hardcoded bullet-points without attempting LLM formatting. It now follows the same pattern as other handlers:
1. Computes data locally
2. Creates bullet-point fallback
3. Tries LLM formatting via `_format_response_with_llm()`
4. Returns LLM response if valid, otherwise uses fallback

With `GEMINI_API_KEY` configured, affordability queries now return conversational responses.

### Email sync data loss

The ETL now uses a try-except wrapper around save_transaction. If the database save fails, the email is NOT moved out of the source folder, preventing data loss.

### ETL environment variables

The ETL validates required environment variables on startup. If any are missing, it will exit with a helpful error message listing the missing variables. Required vars:
- `IMAP_USER`, `IMAP_PASSWORD` - Gmail credentials
- `PG_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS` - PostgreSQL credentials
