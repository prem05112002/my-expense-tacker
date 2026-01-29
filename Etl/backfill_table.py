import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS

def fix_schema():
    print(f"🔧 Connecting to database '{DB_NAME}'...")
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # SQL Commands to add missing columns safely
        commands = [
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS ignored_categories VARCHAR DEFAULT ''",
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS income_categories VARCHAR DEFAULT 'Salary,Income'",
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS view_cycle_offset INTEGER DEFAULT 0",
            # Also ensure budget_value exists if it was missing in older versions
            "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS budget_value FLOAT DEFAULT 50000.0"
        ]
        
        print("🛠️  Applying Schema Updates...")
        for cmd in commands:
            try:
                cur.execute(cmd)
                print(f"   ✅ Success: {cmd}")
            except Exception as e:
                print(f"   ⚠️  Skipped/Error: {e}")
        
        cur.close()
        conn.close()
        print("\n🎉 Database Schema Fixed! You can now restart the backend.")
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("Make sure your database is running and credentials in config.py are correct.")

if __name__ == "__main__":
    fix_schema()