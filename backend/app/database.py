from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# Use 'postgresql+asyncpg' driver
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("PG_HOST")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# Create Async Engine
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Create Async Session Factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

# Dependency for Routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Helper to create tables (Run this once on startup)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)