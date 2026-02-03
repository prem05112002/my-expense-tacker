import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from Etl/.env using absolute path
load_dotenv(Path(__file__).parent / ".env")

# Email Configuration
IMAP_SERVER = "imap.gmail.com"
EMAIL_USER = os.getenv("IMAP_USER")
EMAIL_PASS = os.getenv("IMAP_PASSWORD")

# Folders (Ensure these labels exist in Gmail)
SOURCE_FOLDER = "sync-expense-tracker"
DEST_FOLDER = "expenses"
NON_TXN_FOLDER = "non-transaction"

# Database Configuration
DB_HOST = os.getenv("PG_HOST")
DB_NAME = os.getenv("DB_NAME")
ADMIN_USER = os.getenv("PG_ADMIN_USER")
ADMIN_PASS = os.getenv("PG_ADMIN_PASS")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")


def validate_env():
    """Validate required environment variables at startup."""
    required_vars = {
        "IMAP_USER": EMAIL_USER,
        "IMAP_PASSWORD": EMAIL_PASS,
        "PG_HOST": DB_HOST,
        "DB_NAME": DB_NAME,
        "DB_USER": DB_USER,
        "DB_PASS": DB_PASS,
    }

    missing = [name for name, value in required_vars.items() if not value]

    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\n💡 Create an Etl/.env file with these variables.")
        sys.exit(1)