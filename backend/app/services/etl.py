import sys
import os

try:
    current_dir = os.path.dirname(os.path.abspath(__file__)) # /app
    backend_dir = os.path.dirname(current_dir)               # /backend
    services_dir = os.path.dirname(backend_dir)              # /services
    project_root = os.path.dirname(services_dir)              # / (Root)
    
    etl_path = os.path.join(project_root, "Etl") 
    sys.path.append(etl_path)

    from email_service import EmailService
    from config import SOURCE_FOLDER, DEST_FOLDER, NON_TXN_FOLDER

except ImportError as e:
    print(f"❌ Import Error in services.py: {e}")
    EmailService = None
    SOURCE_FOLDER = "sync-expense-tracker"
    DEST_FOLDER = "expenses"
    NON_TXN_FOLDER = "non-transaction"

def move_email_in_background(uid: str, target_folder: str):
    if not EmailService:
        return

    print(f"🔄 [Background] Moving email UID {uid} to '{target_folder}'...")
    try:
        service = EmailService()
        if service.connect():
            service.mail.select(SOURCE_FOLDER) 
            service.move_email(uid.encode('utf-8'), target_folder)
            service.close()
            print(f"✅ [Background] Moved email {uid} successfully.")
    except Exception as e:
        print(f"❌ [Background] Failed to move email {uid}: {e}")

