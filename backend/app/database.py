from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import os
import re

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("PG_HOST")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?ssl=require"

engine = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


def _safe_schema_name(user_id: str) -> str:
    schema = "u_" + user_id.replace("-", "_")
    if not re.fullmatch(r"u_[a-z0-9_]+", schema):
        raise ValueError(f"Invalid schema name derived from user_id: {schema!r}")
    return schema


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

        # Ensure a user_settings row exists so gmail-setup/save can UPDATE it
        settings_result = await session.execute(text("SELECT COUNT(*) FROM user_settings"))
        if settings_result.scalar() == 0:
            await session.execute(text("""
                INSERT INTO user_settings
                    (salary_day, budget_type, budget_value, ignored_categories, income_categories, view_cycle_offset, imap_configured)
                VALUES
                    (1, 'FIXED', 50000.0, '', 'Salary,Income', 0, FALSE)
            """))
        await session.commit()
