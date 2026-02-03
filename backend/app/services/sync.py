import sys
import os
import asyncio
from datetime import datetime
from typing import Optional
from enum import Enum

# Path setup to import ETL modules
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    services_dir = os.path.dirname(backend_dir)
    project_root = os.path.dirname(services_dir)

    etl_path = os.path.join(project_root, "Etl")
    if etl_path not in sys.path:
        sys.path.append(etl_path)

    # Only import if we can - avoid startup failures
    ETL_AVAILABLE = True
except Exception:
    ETL_AVAILABLE = False


class SyncStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# In-memory sync state (resets on server restart)
_sync_state = {
    "status": SyncStatus.IDLE,
    "started_at": None,
    "completed_at": None,
    "error": None,
    "emails_processed": 0,
    "transactions_saved": 0,
}


def get_sync_status() -> dict:
    """Get current sync status."""
    return {
        "status": _sync_state["status"],
        "started_at": _sync_state["started_at"].isoformat() if _sync_state["started_at"] else None,
        "completed_at": _sync_state["completed_at"].isoformat() if _sync_state["completed_at"] else None,
        "error": _sync_state["error"],
        "emails_processed": _sync_state["emails_processed"],
        "transactions_saved": _sync_state["transactions_saved"],
    }


async def run_email_sync() -> dict:
    """
    Run the ETL pipeline to sync emails.
    Returns the sync status after completion.
    """
    global _sync_state

    # Prevent concurrent syncs
    if _sync_state["status"] == SyncStatus.RUNNING:
        return {"error": "Sync already in progress", **get_sync_status()}

    # Reset state
    _sync_state = {
        "status": SyncStatus.RUNNING,
        "started_at": datetime.now(),
        "completed_at": None,
        "error": None,
        "emails_processed": 0,
        "transactions_saved": 0,
    }

    try:
        print("[Sync] Starting email sync...")

        if not ETL_AVAILABLE:
            raise ImportError("ETL module not available")

        # Import ETL components
        print("[Sync] Importing ETL modules...")
        from database import init_db, save_transaction, save_unmatched, get_db_connection, get_active_rules
        from parsers import extract_metadata, clean_text
        from email_service import EmailService
        from config import SOURCE_FOLDER, DEST_FOLDER
        print("[Sync] ETL modules imported successfully")

        # Run sync in a thread to avoid blocking
        def sync_job():
            print("[Sync] Running sync job in thread...")
            emails_processed = 0
            transactions_saved = 0

            # Initialize
            print("[Sync] Initializing database...")
            init_db()
            active_rules = get_active_rules()
            print(f"[Sync] Loaded {len(active_rules)} automation rules")

            # Connect to email
            print("[Sync] Connecting to IMAP server...")
            service = EmailService()
            if not service.connect():
                raise Exception("Failed to connect to IMAP server")
            print("[Sync] Connected to IMAP server")

            try:
                # Fetch emails
                print(f"[Sync] Fetching emails from '{SOURCE_FOLDER}'...")
                email_ids = service.fetch_emails(SOURCE_FOLDER)

                if not email_ids:
                    print("[Sync] No emails found in source folder")
                    return 0, 0
                print(f"[Sync] Found {len(email_ids)} emails in source folder")

                # Get existing UIDs
                conn = get_db_connection()
                existing_uids = set()
                if conn:
                    cur = conn.cursor()
                    cur.execute("SELECT email_uid FROM unmatched_emails")
                    existing_uids = {row[0] for row in cur.fetchall()}
                    conn.close()

                # Process emails
                for e_id in email_ids:
                    uid_str = e_id.decode('utf-8')

                    if uid_str in existing_uids:
                        continue

                    subject, raw_body = service.get_email_content(e_id)

                    if not raw_body:
                        continue

                    emails_processed += 1
                    cleaned_body = clean_text(raw_body)
                    transaction = extract_metadata(cleaned_body)

                    if transaction:
                        # Apply rules
                        if transaction.merchant_name:
                            for rule in active_rules:
                                is_match = False
                                if rule["type"] == "CONTAINS" and rule["pattern"].lower() in transaction.merchant_name.lower():
                                    is_match = True
                                elif rule["type"] == "EXACT" and rule["pattern"].lower() == transaction.merchant_name.lower():
                                    is_match = True

                                if is_match:
                                    transaction.merchant_name = rule['new_name']
                                    transaction.category_id = rule['cat_id']
                                    break

                        try:
                            save_transaction(transaction)
                            service.move_email(e_id, DEST_FOLDER)
                            transactions_saved += 1
                        except Exception as e:
                            print(f"Failed to save transaction: {e}")
                    else:
                        save_unmatched(uid_str, subject, cleaned_body)

            finally:
                service.close()
                print("[Sync] IMAP connection closed")

            print(f"[Sync] Sync job complete: {emails_processed} processed, {transactions_saved} saved")
            return emails_processed, transactions_saved

        # Run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        emails_processed, transactions_saved = await loop.run_in_executor(None, sync_job)

        _sync_state["emails_processed"] = emails_processed
        _sync_state["transactions_saved"] = transactions_saved
        _sync_state["status"] = SyncStatus.COMPLETED
        _sync_state["completed_at"] = datetime.now()
        print(f"[Sync] Completed successfully: {emails_processed} emails, {transactions_saved} transactions")

    except Exception as e:
        _sync_state["status"] = SyncStatus.FAILED
        _sync_state["error"] = str(e)
        _sync_state["completed_at"] = datetime.now()
        print(f"[Sync] FAILED with error: {str(e)}")
        import traceback
        traceback.print_exc()

    return get_sync_status()
