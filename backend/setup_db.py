# backend/setup_db.py
import os
import sys
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

# --- Shared Configuration ---
# We define these here so we can import them in database.py
# (Single source of truth)
ADMIN_USER = os.getenv("PG_ADMIN_USER")
ADMIN_PASS = os.getenv("PG_ADMIN_PASS")
HOST = os.getenv("PG_HOST")

APP_DB_NAME = 'expense_tracker_test'
APP_USER = 'expense_user'
APP_PASS = 'secure_password_123'

# The final URL your app needs
DATABASE_URL = f"postgresql://{APP_USER}:{APP_PASS}@{HOST}/{APP_DB_NAME}"

def bootstrap_database():
    """
    Connects as ADMIN to create the missing User or Database.
    """
    print(f"⚠️  Database '{APP_DB_NAME}' not found. Calling setup_db to fix...")

    try:
        # Connect to 'postgres' DB as ADMIN
        con = psycopg2.connect(dbname='postgres', user=ADMIN_USER, password=ADMIN_PASS, host=HOST)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()

        # 1. Create User
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (APP_USER,))
        if not cur.fetchone():
            print(f"   👤 Creating user '{APP_USER}'...")
            cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(APP_USER)), (APP_PASS,))
        else:
            print(f"   🔄 Updating password for '{APP_USER}'...")
            cur.execute(sql.SQL("ALTER USER {} WITH PASSWORD %s").format(sql.Identifier(APP_USER)), (APP_PASS,))

        # 2. Create Database
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (APP_DB_NAME,))
        if not cur.fetchone():
            print(f"   📦 Creating database '{APP_DB_NAME}'...")
            cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(APP_DB_NAME), 
                sql.Identifier(APP_USER)
            ))
        
        cur.close()
        con.close()
        print("✅ Bootstrap complete. Ready to connect.")

    except Exception as e:
        print(f"\n❌ BOOTSTRAP ERROR: {e}")
        print("Check your ADMIN_PASS in setup_db.py")
        sys.exit(1)

if __name__ == "__main__":
    # Allows you to run this file manually if you want: python setup_db.py
    bootstrap_database()