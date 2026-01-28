from datetime import datetime
from config import SOURCE_FOLDER, DEST_FOLDER, NON_TXN_FOLDER
from database import init_db, save_transaction, save_unmatched, get_db_connection, get_active_rules
from parsers import extract_metadata, clean_text
from email_service import EmailService

def apply_rules_to_txn(txn, rules):
    """Mutates the transaction object if a rule matches."""
    if not txn.merchant_name: return

    for rule in rules:
        is_match = False
        if rule["type"] == "CONTAINS" and rule["pattern"].lower() in txn.merchant_name.lower():
            is_match = True
        elif rule["type"] == "EXACT" and rule["pattern"].lower() == txn.merchant_name.lower():
            is_match = True
        
        if is_match:
            print(f"✨ Auto-Rule Applied: {txn.merchant_name} -> {rule['new_name']}")
            txn.merchant_name = rule['new_name']
            txn.category_id = rule['cat_id']
            break # Stop after first match

def pipeline_job():
    print(f"\n--- 🚀 Starting Pipeline at {datetime.now()} ---")
    
    # 1. Initialize Infrastructure
    init_db()

    active_rules = get_active_rules()
    if active_rules:
        print(f"🧠 Loaded {len(active_rules)} automation rules.")

    # 2. Connect to Gmail
    service = EmailService()
    if not service.connect(): return

    # 3. Fetch ALL UIDs currently in the Source Folder
    print(f"📂 Scanning Source: {SOURCE_FOLDER}")
    email_ids = service.fetch_emails(SOURCE_FOLDER) # List of bytes [b'101', b'102']
    
    if not email_ids:
        print("📭 No emails found in source folder.")
        service.close()
        return

    # 4. Fetch ALL UIDs already in our Database (The "Ignore List")
    conn = get_db_connection()
    existing_uids = set()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT email_uid FROM unmatched_emails")
        # Convert DB strings to a Set for O(1) lookup
        existing_uids = {row[0] for row in cur.fetchall()} 
        conn.close()

    print(f"📊 Total Emails in Inbox: {len(email_ids)}")
    print(f"🛡️  Already in Review Queue: {len(existing_uids)}")

    # 5. Process only the DELTA (New emails)
    new_count = 0
    
    for e_id in email_ids:
        uid_str = e_id.decode('utf-8')

        # ⚡ CRITICAL: Skip if we already have this in DB
        if uid_str in existing_uids:
            continue
            
        new_count += 1
        subject, raw_body = service.get_email_content(e_id)
        
        if not raw_body: 
            # If completely empty, we might want to skip or log it
            print(f"⚠️ Empty Body for UID {uid_str}. Skipping.")
            continue

        cleaned_body = clean_text(raw_body)
        transaction = extract_metadata(cleaned_body)

        if transaction:
            apply_rules_to_txn(transaction, active_rules)
            # --- SCENARIO A: It IS a Transaction ---
            print(f"✅ Transaction Found: {transaction.amount}")
            save_transaction(transaction)
            
            # Since we are sure, MOVE it out of Inbox immediately
            service.move_email(e_id, DEST_FOLDER)
        else:
            # --- SCENARIO B: Needs Review ---
            print(f"📥 Needs Review: {subject[:40]}...")
            
            # Save to DB so user sees it in UI
            save_unmatched(uid_str, subject, cleaned_body)
            
            # 🛑 IMPORTANT: WE DO NOT MOVE IT.
            # We leave it in 'sync-expenses' so the Frontend can still find it later.

    if new_count == 0:
        print("💤 No new emails to process.")
    else:
        print(f"✨ Processed {new_count} new emails.")

    service.close()
    print("✅ Pipeline Finished.")

if __name__ == "__main__":
    pipeline_job()