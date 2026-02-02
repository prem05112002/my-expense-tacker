# Architectural Patterns

This document describes the key architectural patterns and design decisions used throughout the codebase.

## Backend Patterns

### Router-Service-Schema Pattern

The backend follows a consistent three-layer architecture:

```
Router (HTTP layer) → Service (Business logic) → Database (SQLAlchemy ORM)
```

**Router Layer**: Defines endpoints, validates requests, injects dependencies
- `backend/app/routers/transactions.py:12-26`
- `backend/app/routers/dashboard.py:10-15`
- `backend/app/routers/rules.py:14-31`

**Service Layer**: Contains all business logic, database queries
- `backend/app/services/transactions.py:36-115`
- `backend/app/services/analytics.py:48-180`
- `backend/app/services/rules.py:17-73`

**Schema Layer**: Pydantic models for request/response validation
- `backend/app/schemas/transactions.py:1-43`
- `backend/app/schemas/analytics.py:1-33`

### Dependency Injection via FastAPI Depends()

Database sessions are injected into route handlers using FastAPI's `Depends()`:

```python
async def handler(db: AsyncSession = Depends(get_db)):
```

Pattern locations:
- `backend/app/database.py:30-32` - `get_db()` generator
- `backend/app/routers/transactions.py:13` - Usage example
- `backend/app/routers/staging.py:16-20` - With BackgroundTasks

### Async-First Database Operations

All database operations use async SQLAlchemy:
- Engine: `create_async_engine()` - `backend/app/database.py:9-14`
- Session: `AsyncSession` with `expire_on_commit=False` - `backend/app/database.py:15-20`
- Queries: `await session.execute()` - `backend/app/services/transactions.py:77-91`

### Pagination Pattern

Consistent pagination across list endpoints:

```python
class PaginatedResponse(BaseModel):
    items: list[ItemSchema]
    total: int
    page: int
    total_pages: int
```

Implemented at:
- Schema: `backend/app/schemas/transactions.py:14-19`
- Service: `backend/app/services/transactions.py:65-74` (count query)
- Router: `backend/app/routers/transactions.py:12-26` (page/limit params)

### Dynamic Query Building

Filters are applied conditionally to base queries:

```python
query = select(Model)
if filter_value:
    query = query.where(Model.field == filter_value)
```

Examples:
- `backend/app/services/transactions.py:48-63` - Multiple optional filters
- `backend/app/services/analytics.py:91-130` - Date range and category filters

### Background Tasks for Non-Blocking Operations

FastAPI's BackgroundTasks for async operations that shouldn't block response:

- `backend/app/routers/staging.py:16-20` - Email folder movement
- `backend/app/services/etl.py:20-37` - Background email operations

## Frontend Patterns

### React Hooks State Management

Each page manages its own state using React hooks with clear separation:

```javascript
const [data, setData] = useState([]);           // API data
const [loading, setLoading] = useState(true);   // UI state
const [page, setPage] = useState(1);            // Pagination
const [filters, setFilters] = useState({...});  // Filter state
```

Pattern locations:
- `frontend/src/pages/Transactions.jsx:15-44`
- `frontend/src/pages/Dashboard.jsx:12-31`

### Effect Hook with Dependencies

Data fetching triggered by state changes:

```javascript
useEffect(() => {
    fetchData();
}, [page, filters, sortConfig]);
```

Examples:
- `frontend/src/pages/Transactions.jsx:46-60`
- `frontend/src/pages/Dashboard.jsx:33-45`

### Centralized API Client

Single Axios instance with base configuration:
- `frontend/src/api/axios.js:1-10`
- Used throughout pages for consistent API calls

### Component Composition

Reusable UI components in `frontend/src/components/`:
- `Layout.jsx` - Page wrapper with sidebar
- `Sidebar.jsx` - Navigation component
- `ui/` - Atomic components (DateFilter, SortableHeader, etc.)

## Data Patterns

### Rule Application Pattern

Rules are applied at two points:
1. **ETL ingestion**: `Etl/main.py:7-22` - When emails are processed
2. **Historical application**: `backend/app/services/rules.py:33-49` - Bulk update existing transactions

Rule matching supports CONTAINS and EXACT modes:
- `backend/app/services/rules.py:59-73`

### Salary Cycle Calculation

Financial periods based on configurable payday:
- Weekend adjustment: `backend/app/services/analytics.py:8-19`
- Cycle date calculation: `backend/app/services/analytics.py:21-45`
- Secure cycle (prevents double-counting): `backend/app/services/analytics.py:48-89`

### Duplicate Detection

Two-phase duplicate matching:
1. Group by exact amount (O(1) lookup)
2. Fuzzy string matching within groups using RapidFuzz

Implementation: `backend/app/services/duplicates.py:35-70`

## API Design Conventions

### Endpoint Naming
- Resources are plural nouns: `/transactions`, `/categories`, `/rules`
- Actions use verbs: `/staging/{id}/approve`, `/staging/{id}/dismiss`

### Response Models
- List endpoints return `PaginatedResponse` wrapper
- Single items return the schema directly
- All schemas use `from_attributes=True` for ORM compatibility

### Query Parameters
- Filtering: `?category_id=1&bank=HDFC`
- Pagination: `?page=1&limit=15`
- Sorting: `?sort_by=date&sort_order=desc`
- Search: `?search=grocery`

## Database Conventions

### Model Relationships
All relationships use SQLAlchemy's `relationship()` with explicit foreign keys:
- `backend/app/models.py:26-27` - Transaction → Category
- `backend/app/models.py:36-37` - TransactionRule → Category

### Table Naming
Tables use snake_case plural names: `transactions`, `categories`, `transaction_rules`

### Common Fields
- `id`: Auto-increment primary key
- `created_at`/`updated_at`: Timestamps (where applicable)
- Foreign keys follow pattern: `{related_table_singular}_id`
