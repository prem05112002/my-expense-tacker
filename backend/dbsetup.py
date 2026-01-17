import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

def bootstrap_database():
    # ---------------- CONFIGURATION ----------------
    ADMIN_USER = 'postgres'
    # ⚠️ ENSURE THIS MATCHES YOUR POSTGRES INSTALL PASSWORD
    ADMIN_PASS = 'Crazyisme@5'  
    HOST = 'localhost'

    APP_DB_NAME = 'expense_tracker_test'
    APP_USER = 'expense_user'
    APP_PASS = 'secure_password_123'
    # -----------------------------------------------

    print(f"🔧 Connecting to 'postgres' to check setup...")
    
    try:
        con = psycopg2.connect(dbname='postgres', user=ADMIN_USER, password=ADMIN_PASS, host=HOST)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()

        # 1. Ensure User Exists & FORCE UPDATE PASSWORD
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (APP_USER,))
        if not cur.fetchone():
            print(f"👤 Creating user '{APP_USER}'...")
            cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(APP_USER)), (APP_PASS,))
        else:
            print(f"🔄 User '{APP_USER}' exists. Updating password to match script...")
            # This line fixes your error:
            cur.execute(sql.SQL("ALTER USER {} WITH PASSWORD %s").format(sql.Identifier(APP_USER)), (APP_PASS,))

        # 2. Check/Create Database
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (APP_DB_NAME,))
        if not cur.fetchone():
            print(f"📦 Creating database '{APP_DB_NAME}'...")
            cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(APP_DB_NAME), 
                sql.Identifier(APP_USER)
            ))
        else:
            print(f"✅ Database '{APP_DB_NAME}' already exists.")

        cur.close()
        con.close()
        print("🚀 Database bootstrapping complete.\n")
        
        return f'postgresql://{APP_USER}:{APP_PASS}@{HOST}/{APP_DB_NAME}'

    except Exception as e:
        print(f"\n❌ CRITICAL DATABASE ERROR: {e}")
        print(f"👉 Tip: Double check that ADMIN_PASS='{ADMIN_PASS}' is actually your local postgres password.")
        sys.exit(1)

if __name__ == "__main__":
    bootstrap_database()