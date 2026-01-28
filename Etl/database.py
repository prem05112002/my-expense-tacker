import psycopg2
import sys
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, ADMIN_USER, ADMIN_PASS

# --- INFRASTRUCTURE BOOTSTRAP ---
def bootstrap_infrastructure():
    """Step 0: Create the Postgres User and Database if they don't exist."""
    print(f"🔧 Checking Infrastructure for '{DB_NAME}'...")
    try:
        con = psycopg2.connect(dbname='postgres', user=ADMIN_USER, password=ADMIN_PASS, host=DB_HOST)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()

        cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (DB_USER,))
        if not cur.fetchone():
            print(f"   👤 Creating user '{DB_USER}'...")
            cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(DB_USER)), (DB_PASS,))
        
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
        if not cur.fetchone():
            print(f"   📦 Creating database '{DB_NAME}'...")
            cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(DB_NAME), sql.Identifier(DB_USER)))
        
        cur.close()
        con.close()
        print("✅ Infrastructure Ready.")
    except Exception as e:
        print(f"\n❌ INFRASTRUCTURE ERROR: {e}")

# --- HELPER: SAFE TRUNCATION ---
def truncate(text, max_length):
    """Safely truncates string to max_length, handling None."""
    if text and len(text) > max_length:
        return text[:max_length]
    return text

# --- HELPER: CATEGORY PREDICTION ---
def get_predicted_category(cur, merchant_name):
    """
    Checks if a rule exists for this merchant.
    Matches if the merchant name CONTAINS the keyword (Case Insensitive).
    """
    if not merchant_name: return None
    
    # ILIKE '%%' || keyword || '%%' allows partial matching
    # e.g., Rule "Zomato" matches merchant "Zomato UPI"
    cur.execute("""
        SELECT category_id FROM category_rules 
        WHERE %s ILIKE '%%' || keyword || '%%' 
        LIMIT 1
    """, (merchant_name,))
    
    row = cur.fetchone()
    return row[0] if row else None

# --- STANDARD DATABASE OPERATIONS ---

def get_db_connection():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        return conn
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return None

def init_db():
    bootstrap_infrastructure()
    conn = get_db_connection()
    if not conn: return
    
    # 1. Create Tables
    commands = [
        # Categories Table
        """
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            color VARCHAR(20) DEFAULT '#94a3b8'
        )
        """,
        # Seed Default Categories (Only if they don't exist)
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
        # Rules Table
        """
        CREATE TABLE IF NOT EXISTS category_rules (
            id SERIAL PRIMARY KEY,
            keyword VARCHAR(100) NOT NULL,
            category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # Transactions Table (Modified with category_id)
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
            category_id INTEGER REFERENCES categories(id), -- New Column
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # Unmatched Emails Table
        """
        CREATE TABLE IF NOT EXISTS unmatched_emails (
            id SERIAL PRIMARY KEY,
            email_uid VARCHAR(50) UNIQUE,
            email_subject TEXT,
            email_body TEXT,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]
    
    try:
        cur = conn.cursor()
        for command in commands:
            cur.execute(command)
        
        # 2. Schema Migration Check
        # If table existed before, ensure category_id column is added
        cur.execute("SELECT to_regclass('public.transactions')")
        if cur.fetchone()[0]:
            try:
                cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES categories(id)")
                # Set default category for existing rows that are NULL
                cur.execute("""
                    UPDATE transactions 
                    SET category_id = (SELECT id FROM categories WHERE name = 'Uncategorized') 
                    WHERE category_id IS NULL
                """)
            except Exception as e:
                print(f"⚠️ Migration warning: {e}")

        conn.commit()
        print("✅ Database tables checked/created.")
    except Exception as e:
        print(f"❌ Table Creation Error: {e}")
    finally:
        if conn: conn.close()

def check_soft_duplicate(cur, txn):
    """Checks if a similar transaction exists. Returns ID if found."""
    s_merch = truncate(txn.merchant_name, 255)
    
    query = """
        SELECT id FROM transactions 
        WHERE amount = %s 
        AND txn_date = %s 
        AND merchant_name = %s 
        AND payment_mode = %s
        LIMIT 1
    """
    cur.execute(query, (txn.amount, txn.date, s_merch, txn.payment_mode))
    row = cur.fetchone()
    return row[0] if row else None

# ✅ 1. NEW Helper to fetch Rules
def get_active_rules():
    """Fetches all cleanup rules to apply during ETL."""
    conn = get_db_connection()
    if not conn: return []
    try:
        cur = conn.cursor()
        # Fetch pattern, new_name, category_id, match_type
        cur.execute("SELECT pattern, new_merchant_name, category_id, match_type FROM transaction_rules")
        rows = cur.fetchall()
        rules = [
            {"pattern": r[0], "new_name": r[1], "cat_id": r[2], "type": r[3]} 
            for r in rows
        ]
        return rules
    except Exception as e:
        print(f"⚠️ Failed to fetch rules: {e}")
        return []
    finally:
        conn.close()

def save_transaction(txn):
    conn = get_db_connection()
    if not conn: return

    try:
        cur = conn.cursor()
        
        # --- PREPARE DATA ---
        t_bank = truncate(txn.bank_name, 50)
        t_mode = truncate(txn.payment_mode, 20)
        t_upi = truncate(txn.upi_id, 255)
        t_merch = truncate(txn.merchant_name, 255)
        t_ref = truncate(txn.upi_transaction_id, 100)
        
        # --- DETERMINE CATEGORY ---
        # 1. Get Default "Uncategorized" ID
        cur.execute("SELECT id FROM categories WHERE name = 'Uncategorized'")
        default_cat_id = cur.fetchone()[0]

        # 2. Check Rules Engine
        predicted_cat_id = get_predicted_category(cur, t_merch)
        final_cat_id = predicted_cat_id if predicted_cat_id else default_cat_id

        # --- INSERTION LOGIC ---
        
        # SCENARIO 1: UPI Transaction (HARD STOP)
        if t_ref:
            cur.execute("""
                INSERT INTO transactions 
                (bank_name, amount, payment_type, account_num, payment_mode, txn_date, upi_id, merchant_name, upi_transaction_id, category_id, potential_duplicate_of_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                ON CONFLICT (upi_transaction_id) DO NOTHING;
            """, (t_bank, txn.amount, txn.payment_type, txn.account_num, 
                  t_mode, txn.date, t_upi, t_merch, t_ref, final_cat_id))
            
        # SCENARIO 2: Non-UPI Transaction (SOFT STOP / LINK)
        else:
            # Check for duplicate
            original_txn_id = check_soft_duplicate(cur, txn)
            
            if original_txn_id:
                print(f"🚩 Soft Duplicate Flagged: Linked to Transaction ID #{original_txn_id}")
            
            final_cat_id = txn.category_id if txn.category_id else None

            cur.execute("""
                INSERT INTO transactions 
                (bank_name, amount, payment_type, account_num, payment_mode, txn_date, upi_id, merchant_name, upi_transaction_id, category_id, potential_duplicate_of_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s)
            """, (txn.bank_name, txn.amount, txn.payment_type, txn.account_num, 
                txn.payment_mode, txn.date, txn.upi_id, txn.merchant_name, final_cat_id, original_txn_id))

        conn.commit()
    except Exception as e:
        print(f"❌ DB Insert Error: {e}")
        conn.rollback()
    finally:
        conn.close()

def save_unmatched(email_uid, subject, body):
    """Saves non-transaction emails. Skips if UID already exists."""
    conn = get_db_connection()
    if not conn: return

    try:
        cur = conn.cursor()
        # ✅ FIX: Use ON CONFLICT DO NOTHING to prevent crashes
        cur.execute("""
            INSERT INTO unmatched_emails (email_uid, email_subject, email_body, received_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (email_uid) DO NOTHING
        """, (str(email_uid), subject, body))
        
        conn.commit()
    except Exception as e:
        print(f"❌ Error saving unmatched email: {e}")
        conn.rollback()
    finally:
        conn.close()