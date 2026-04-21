"""
Database setup: creates PostgreSQL user, database, and all application tables.
Table schemas must stay in sync with backend/app/models.py.
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

    # -----------------------------------------------------------------------
    # CREATE TABLE statements — must match backend/app/models.py exactly
    # -----------------------------------------------------------------------
    create_commands = [
        # categories — model: Category
        """
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            color VARCHAR(20) DEFAULT '#94a3b8',
            is_income BOOLEAN DEFAULT FALSE
        )
        """,
        # Default categories (seeded once)
        """
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
        """,
        # transaction_rules — model: TransactionRule
        """
        CREATE TABLE IF NOT EXISTS transaction_rules (
            id SERIAL PRIMARY KEY,
            pattern VARCHAR(255),
            new_merchant_name VARCHAR(255),
            match_type VARCHAR(20) DEFAULT 'CONTAINS',
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL
        )
        """,
        # transactions — model: Transaction
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            merchant_name VARCHAR(255),
            amount DECIMAL(10, 2),
            txn_date DATE,
            payment_mode VARCHAR(20),
            payment_type VARCHAR(10),
            bank_name VARCHAR(50),
            upi_transaction_id VARCHAR(100) UNIQUE,
            category_id INTEGER REFERENCES categories(id)
        )
        """,
        # unmatched_emails — model: StagingTransaction
        """
        CREATE TABLE IF NOT EXISTS unmatched_emails (
            id SERIAL PRIMARY KEY,
            email_uid VARCHAR(50) UNIQUE,
            email_subject VARCHAR(255),
            email_body TEXT,
            received_at TIMESTAMP
        )
        """,
        # ignored_duplicates — model: IgnoredDuplicate
        """
        CREATE TABLE IF NOT EXISTS ignored_duplicates (
            id SERIAL PRIMARY KEY,
            txn1_id INTEGER,
            txn2_id INTEGER
        )
        """,
        # user_settings — model: UserSettings
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            id SERIAL PRIMARY KEY,
            salary_day INTEGER DEFAULT 1,
            monthly_budget DECIMAL(10, 2),
            budget_type VARCHAR(20) DEFAULT 'FIXED',
            budget_value DECIMAL(10, 2),
            ignored_categories TEXT DEFAULT '',
            income_categories TEXT DEFAULT 'Salary,Income',
            view_cycle_offset INTEGER DEFAULT 0
        )
        """,
        # recurring_expenses — model: RecurringExpense
        """
        CREATE TABLE IF NOT EXISTS recurring_expenses (
            id SERIAL PRIMARY KEY,
            merchant_name VARCHAR(255),
            amount DECIMAL(10, 2),
            frequency VARCHAR(20),
            next_due_date DATE,
            last_transaction_id INTEGER REFERENCES transactions(id)
        )
        """,
        # monthly_goals — model: MonthlyGoal
        """
        CREATE TABLE IF NOT EXISTS monthly_goals (
            id SERIAL PRIMARY KEY,
            category_id INTEGER REFERENCES categories(id) NOT NULL,
            cap_amount DECIMAL(10, 2) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_via VARCHAR(20) DEFAULT 'manual'
        )
        """,
    ]

    # -----------------------------------------------------------------------
    # Migration commands — add columns missing from older installations.
    # Safe to run on a fresh install (IF NOT EXISTS / DO NOTHING).
    # -----------------------------------------------------------------------
    migration_commands = [
        # categories: added is_income
        "ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_income BOOLEAN DEFAULT FALSE",

        # transaction_rules: drop the old NOT-NULL keyword constraint so existing
        # installs don't reject inserts from the backend (which never sends keyword)
        "ALTER TABLE transaction_rules ALTER COLUMN keyword DROP NOT NULL",

        # transactions: ensure category_id exists (legacy installs may lack it)
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id)",

        # user_settings: added budget_type, budget_value, income_categories
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS budget_type VARCHAR(20) DEFAULT 'FIXED'",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS budget_value DECIMAL(10,2)",
        "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS income_categories TEXT DEFAULT 'Salary,Income'",

        # recurring_expenses: old schema used last_seen + category_id; new schema uses next_due_date + last_transaction_id
        "ALTER TABLE recurring_expenses ADD COLUMN IF NOT EXISTS next_due_date DATE",
        "ALTER TABLE recurring_expenses ADD COLUMN IF NOT EXISTS last_transaction_id INTEGER REFERENCES transactions(id)",

        # monthly_goals: old schema used month/year/budget; new schema uses cap_amount/is_active/created_at/created_via
        "ALTER TABLE monthly_goals ADD COLUMN IF NOT EXISTS cap_amount DECIMAL(10,2)",
        "ALTER TABLE monthly_goals ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE monthly_goals ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE monthly_goals ADD COLUMN IF NOT EXISTS created_via VARCHAR(20) DEFAULT 'manual'",

        # ignored_duplicates: old schema used transaction_id; new schema uses txn1_id + txn2_id
        "ALTER TABLE ignored_duplicates ADD COLUMN IF NOT EXISTS txn1_id INTEGER",
        "ALTER TABLE ignored_duplicates ADD COLUMN IF NOT EXISTS txn2_id INTEGER",
    ]

    try:
        cur = conn.cursor()

        # Phase 1: create tables and seed — commit atomically
        for cmd in create_commands:
            cur.execute(cmd)
        conn.commit()

        # Phase 2: migrations — each runs in its own savepoint so a single failure
        # doesn't roll back the others
        for cmd in migration_commands:
            try:
                cur.execute("SAVEPOINT migration_step")
                cur.execute(cmd)
                cur.execute("RELEASE SAVEPOINT migration_step")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT migration_step")

        # Phase 3: back-fill transactions that have no category
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
