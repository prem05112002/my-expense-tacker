from re import sub
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import init_db
from .routers import transactions, dashboard, categories, staging, rules, subscription

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server starting... checking tables.")
    await init_db()
    yield
    print("🛑 Server shutting down.")

app = FastAPI(title="Expense Tracker API", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(dashboard.router)
app.include_router(transactions.router)
app.include_router(categories.router)
app.include_router(staging.router)
app.include_router(rules.router)
app.include_router(subscription.router)

@app.get("/")
def read_root():
    return {"status": "✅ API is running"}