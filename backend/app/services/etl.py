from ..etl.email_service import EmailService

SOURCE_FOLDER = "sync-expense-tracker"
DEST_FOLDER = "expenses"
NON_TXN_FOLDER = "non-transaction"


def move_email_in_background(uid: str, target_folder: str, imap_user: str, imap_pass: str):
    print(f"[Background] Moving email UID {uid} to '{target_folder}'...")
    try:
        service = EmailService(imap_user, imap_pass)
        if service.connect():
            service.mail.select(SOURCE_FOLDER)
            service.move_email(uid.encode('utf-8'), target_folder)
            service.close()
            print(f"[Background] Moved email {uid} successfully.")
    except Exception as e:
        print(f"[Background] Failed to move email {uid}: {e}")

