# backend/setup_db.py
import os
import sys
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import your models to create tables and seed data
from database import Base, DATABASE_URL # Ensure database.py exports this URL
from models import GlobalBank

load_dotenv()

# --- Admin Config ---
ADMIN_USER = os.getenv("PG_ADMIN_USER", "postgres")
ADMIN_PASS = os.getenv("PG_ADMIN_PASS", "password")
HOST = os.getenv("PG_HOST", "localhost")

# --- App Config ---
APP_DB_NAME = 'expense_tracker_test'
APP_USER = 'expense_user'
APP_PASS = 'secure_password_123'

INITIAL_BANKS = [
    # SBI
    {"name": "SBI", "email": "cbssbi.cas@alerts.sbi.co.in"},
    {"name": "SBI", "email": "alerts@alerts.sbi.co.in"},
    {"name": "SBI", "email": "no-reply@alerts.sbi.co.in"},

    # HDFC
    {"name": "HDFC", "email": "alerts@hdfcbank.net"},
    {"name": "HDFC", "email": "no-reply@hdfcbank.net"},
    {"name": "HDFC", "email": "alerts@alerts.hdfcbank.net"},

    # ICICI
    {"name": "ICICI", "email": "alerts@icicibank.com"},
    {"name": "ICICI", "email": "no-reply@icicibank.com"},

    # Axis
    {"name": "Axis Bank", "email": "alerts@axisbank.com"},
    {"name": "Axis Bank", "email": "no-reply@axisbank.com"},

    # Kotak
    {"name": "Kotak", "email": "alerts@kotak.com"},
    {"name": "Kotak", "email": "no-reply@kotak.com"},

    # Others
    {"name": "IDFC First", "email": "alerts@idfcfirstbank.com"},
    {"name": "Yes Bank", "email": "alerts@yesbank.in"},
]

def bootstrap_infrastructure():
    """Step 1: Create the Postgres User and Database if they don't exist."""
    print(f"🔧 Checking Infrastructure for '{APP_DB_NAME}'...")

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
        print("✅ Infrastructure Ready.")

    except Exception as e:
        print(f"\n❌ INFRASTRUCTURE ERROR: {e}")
        print("Check your ADMIN_PASS in .env or setup_db.py")
        sys.exit(1)

def init_schema_and_seed():
    """Step 2 & 3: Create Tables and Seed Initial Data."""
    print("🌱 Initializing Schema & Seeding Data...")
    
    # Connect to the NEW App Database
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # A. Create Tables
    Base.metadata.create_all(bind=engine)
    print("   ✅ Tables Created.")
    
    # B. Seed Data
    db = SessionLocal()
    try:
        count = 0
        for bank in INITIAL_BANKS:
            # Check if exists to avoid duplicates
            exists = db.query(GlobalBank).filter_by(sender_email=bank["email"]).first()
            if not exists:
                new_bank = GlobalBank(name=bank["name"], sender_email=bank["email"])
                db.add(new_bank)
                count += 1
        
        db.commit()
        if count > 0:
            print(f"   ✅ Seeded {count} new banks into Global Registry.")
        else:
            print("   🔹 Global Registry already up to date.")
            
    except Exception as e:
        print(f"❌ SEED ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    bootstrap_infrastructure()
    init_schema_and_seed()
    print("\n🚀 Database Setup Complete! You can now start the backend.")