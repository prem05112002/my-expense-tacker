import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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