from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .routers import transactions, dashboard, categories, staging, rules, subscription, trends, chatbot, sync, goals, provision, gmail_setup


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server starting.")
    yield
    print("🛑 Server shutting down.")

app = FastAPI(title="Expense Tracker API", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://my-expense-tacker.vercel.app",
    ],
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
app.include_router(trends.router)
app.include_router(chatbot.router)
app.include_router(sync.router)
app.include_router(goals.router)
app.include_router(provision.router)
app.include_router(gmail_setup.router)


@app.get("/")
def read_root():
    return {"status": "✅ API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
