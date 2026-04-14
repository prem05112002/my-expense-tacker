"""
Database setup: creates PostgreSQL user, database, and all application tables.
Refactored from Etl/database.py — takes credentials as parameters instead of reading from env.
"""
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_HOST = "localhost"
DEFAULT_DB_NAME = "expense_tracker"
DEFAULT_DB_USER = "tracker_user"


def setup_database(admin_pass: str, db_pass: str) -> dict:
    """Full setup: create user, database, and all tables."""
    try:
        _bootstrap_infrastructure(admin_pass, db_pass)
        _init_tables(db_pass)
        return {"ok": True, "message": "Database and tables created successfully."}
    except psycopg2.OperationalError as e:
        msg = str(e).strip()
        if "password authentication failed" in msg or "role" in msg.lower():
            return {
                "ok": False,
                "message": "Wrong PostgreSQL admin password. Please check and try again.",
            }
        if "Connection refused" in msg or "could not connect" in msg.lower():
            return {
                "ok": False,
                "message": (
                    "Could not connect to PostgreSQL. "
                    "Make sure PostgreSQL is installed and running."
                ),
            }
        return {"ok": False, "message": f"Database error: {msg}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _bootstrap_infrastructure(admin_pass: str, db_pass: str) -> None:
    con = psycopg2.connect(
        dbname="postgres", user="postgres", password=admin_pass, host=DB_HOST
    )
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()

    # Create app user if it doesn't exist
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (DEFAULT_DB_USER,))
    if not cur.fetchone():
        cur.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                sql.Identifier(DEFAULT_DB_USER)
            ),
            (db_pass,),
        )

    # Create database if it doesn't exist
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DEFAULT_DB_NAME,))
    if not cur.fetchone():
        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(DEFAULT_DB_NAME), sql.Identifier(DEFAULT_DB_USER)
            )
        )

    cur.close()
    con.close()


def _init_tables(db_pass: str) -> None:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DEFAULT_DB_NAME,
        user=DEFAULT_DB_USER,
        password=db_pass,
    )
    commands = [
        """
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            color VARCHAR(20) DEFAULT '#94a3b8'
        )
        """,
        """
        INSERT INTO categories (name, color) VALUES
            ('Food', '#f87171'),
            ('Transport', '#60a5fa'),
            ('Shopping', '#c084fc'),
            ('Bills', '#fbbf24'),
            ('Health', '#4ade80'),
            ('Uncategorized', '#cbd5e1')
        ON CONFLICT (name) DO NOTHING
        """,
        """
        CREATE TABLE IF NOT EXISTS transaction_rules (
            id SERIAL PRIMARY KEY,
            keyword VARCHAR(100) NOT NULL,
            pattern VARCHAR(255),
            new_merchant_name VARCHAR(255),
            match_type VARCHAR(20) DEFAULT 'CONTAINS',
            category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            bank_name VARCHAR(50),
            amount DECIMAL(10, 2),
            payment_type VARCHAR(10),
            account_num BIGINT,
            payment_mode VARCHAR(20),
            txn_date DATE,
            upi_id VARCHAR(255),
            merchant_name VARCHAR(255),
            upi_transaction_id VARCHAR(100) UNIQUE,
            potential_duplicate_of_id INTEGER REFERENCES transactions(id),
            category_id INTEGER REFERENCES categories(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS unmatched_emails (
            id SERIAL PRIMARY KEY,
            email_uid VARCHAR(50) UNIQUE,
            email_subject TEXT,
            email_body TEXT,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ignored_duplicates (
            id SERIAL PRIMARY KEY,
            transaction_id INTEGER REFERENCES transactions(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            id SERIAL PRIMARY KEY,
            salary_day INTEGER DEFAULT 1,
            monthly_budget DECIMAL(10, 2),
            ignored_categories TEXT[],
            view_cycle_offset INTEGER DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS recurring_expenses (
            id SERIAL PRIMARY KEY,
            merchant_name VARCHAR(255),
            amount DECIMAL(10, 2),
            frequency VARCHAR(20),
            last_seen DATE,
            category_id INTEGER REFERENCES categories(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS monthly_goals (
            id SERIAL PRIMARY KEY,
            category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
            month INTEGER,
            year INTEGER,
            budget DECIMAL(10, 2),
            UNIQUE(category_id, month, year)
        )
        """,
        # Ensure category_id column exists on transactions (migration safety)
        """
        ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id)
        """,
    ]

    try:
        cur = conn.cursor()
        for cmd in commands:
            cur.execute(cmd)
        # Back-fill nulls in category_id
        cur.execute(
            """
            UPDATE transactions
            SET category_id = (SELECT id FROM categories WHERE name = 'Uncategorized')
            WHERE category_id IS NULL
            """
        )
        conn.commit()
    finally:
        conn.close()
