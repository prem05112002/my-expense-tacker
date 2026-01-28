import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, NON_TXN_FOLDER
from email_service import EmailService
from parsers import clean_text

def get_db_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
    except Exception as e:
        print(f"❌ DB Connection Error: {e}")
        return None

def reload_job():
    print("--- ☢️  STARTING FULL RELOAD OF NON-TRANSACTIONS ☢️  ---")

    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()

    # 1. TRUNCATE THE TABLE (Wipe it clean)
    print("🗑️  Truncating 'unmatched_emails' table...")
    try:
        # RESTART IDENTITY resets the ID counter back to 1
        cur.execute("TRUNCATE TABLE unmatched_emails RESTART IDENTITY;")
        conn.commit()
        print("✅ Table wiped successfully.")
    except Exception as e:
        print(f"❌ Error truncating table: {e}")
        return

    # 2. CONNECT TO GMAIL
    service = EmailService()
    if not service.connect():
        return

    print(f"📂 Selecting Gmail folder: '{NON_TXN_FOLDER}'...")
    try:
        service.mail.select(NON_TXN_FOLDER)
    except Exception as e:
        print(f"❌ Could not select folder. Make sure '{NON_TXN_FOLDER}' exists.")
        return

    # 3. FETCH ALL EMAILS
    # We fetch ALL UIDs currently in this folder
    status, messages = service.mail.uid('search', None, "ALL")
    
    if not messages or not messages[0]:
        print("✅ No emails found in non-transaction folder. Nothing to import.")
        return

    email_uids = messages[0].split()
    total_emails = len(email_uids)
    print(f"📥 Found {total_emails} emails. Starting import...")

    # 4. PROCESS AND INSERT
    count = 0
    for e_uid in email_uids:
        try:
            # Helper to convert bytes UID to string
            uid_str = e_uid.decode('utf-8')
            
            # Fetch Content
            subject, raw_body = service.get_email_content(e_uid)
            
            if not raw_body:
                raw_body = "" # Handle cases with no body

            # Clean the body (HTML to Text)
            cleaned_body = clean_text(raw_body)

            # Insert into DB
            cur.execute("""
                INSERT INTO unmatched_emails (email_uid, email_subject, email_body, received_at)
                VALUES (%s, %s, %s, NOW())
            """, (uid_str, subject, cleaned_body))
            
            count += 1
            if count % 10 == 0:
                print(f"   ⏳ Imported {count}/{total_emails}...")

        except Exception as e:
            print(f"   ⚠️ Error importing UID {e_uid}: {e}")

    # 5. COMMIT AND CLOSE
    conn.commit()
    cur.close()
    conn.close()
    service.close()

    print(f"\n--- ✅ RELOAD COMPLETE ---")
    print(f"Total Imported: {count}")

if __name__ == "__main__":
    reload_job()
