from datetime import datetime
from config import SOURCE_FOLDER, DEST_FOLDER, NON_TXN_FOLDER
from database import init_db, save_transaction, save_unmatched
from parsers import extract_metadata, clean_text
from email_service import EmailService

def pipeline_job():
    print(f"\n--- 🚀 Starting Pipeline at {datetime.now()} ---")
    
    # 1. Initialize DB
    init_db()

    # 2. Connect to Email
    service = EmailService()
    if not service.connect():
        return

    # 3. Fetch Emails (Returns UIDs now)
    email_ids = service.fetch_emails(SOURCE_FOLDER)
    print(f"📬 Found {len(email_ids)} emails in {SOURCE_FOLDER}")

    if not email_ids:
        service.close()
        return

    # 4. Process Each Email
    for e_id in email_ids:
        # e_id is bytes (e.g. b'1402'), convert to string for DB
        uid_str = e_id.decode('utf-8')
        
        subject, raw_body = service.get_email_content(e_id)
        
        # Skip if body is empty
        if not raw_body: 
            print(f"⚠️ Empty Body: {subject}")
            service.move_email(e_id, NON_TXN_FOLDER)
            continue

        cleaned_body = clean_text(raw_body)
        transaction = extract_metadata(cleaned_body)

        if transaction:
            # --- SUCCESS CASE ---
            print(f"✅ Matched: {transaction.payment_mode} | {transaction.amount}")
            save_transaction(transaction)
            service.move_email(e_id, DEST_FOLDER)
        else:
            # --- FAILURE CASE ---
            print(f"❌ Unmatched: {subject} -> Moving to NonTransaction")
            
            save_unmatched(uid_str, subject, cleaned_body)
            
            service.move_email(e_id, NON_TXN_FOLDER)

    # 5. Cleanup
    service.close()
    print("--- ✅ Pipeline Finished ---")

if __name__ == "__main__":
    pipeline_job()