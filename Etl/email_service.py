import imaplib
import email
from email.header import decode_header
from config import IMAP_SERVER, EMAIL_USER, EMAIL_PASS

class EmailService:
    def __init__(self):
        self.mail = None

    def connect(self):
        """Connects to IMAP Server"""
        try:
            self.mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            self.mail.login(EMAIL_USER, EMAIL_PASS)
            print("✅ Connected to IMAP")
            return True
        except Exception as e:
            print(f"❌ IMAP Connection Failed: {e}")
            return False

    def fetch_emails(self, folder):
        """Selects folder and fetches list of email UIDs"""
        try:
            status, _ = self.mail.select(folder)
            if status != "OK":
                print(f"❌ Cannot select folder {folder}")
                return []
            
            # --- CHANGE 1: Use UID Search ---
            # This returns persistent IDs (UIDs) instead of dynamic sequence numbers
            status, messages = self.mail.uid('search', None, "ALL")
            
            if not messages or not messages[0]:
                return []
                
            return messages[0].split()
        except Exception as e:
            print(f"❌ Fetch Error: {e}")
            return []

    def get_email_content(self, email_id):
        """Fetches Subject and Body for a specific Email UID"""
        try:
            # --- CHANGE 2: Use UID Fetch ---
            _, msg_data = self.mail.uid('fetch', email_id, "(RFC822)")
            
            if not msg_data or msg_data[0] is None:
                print(f"⚠️ Could not fetch email UID {email_id}")
                return None, None

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Subject
            subject_header = msg.get("Subject")
            if subject_header:
                subject, encoding = decode_header(subject_header)[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
            else:
                subject = "No Subject"

            # Body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload: body = payload.decode()
                        break
                    elif part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload: body = payload.decode() # Cleaned later
            else:
                payload = msg.get_payload(decode=True)
                if payload: body = payload.decode()
            
            return subject, body
        except Exception as e:
            print(f"❌ Error parsing email {email_id}: {e}")
            return None, None

    def move_email(self, email_id, dest_folder):
        """Moves email to destination folder using UID"""
        try:
            # --- CHANGE 3: Use UID Copy and UID Store ---
            copy_res = self.mail.uid('copy', email_id, dest_folder)
            if copy_res[0] == 'OK':
                self.mail.uid('store', email_id, '+FLAGS', '\\Deleted')
            else:
                print(f"⚠️ Failed to copy email {email_id}")
        except imaplib.IMAP4.error as e:
            print(f"❌ IMAP Move Error: {e}")
        except Exception as e:
            print(f"❌ Unexpected Move Error: {e}")

    def close(self):
        """Expunges and closes connection"""
        if self.mail:
            try:
                self.mail.expunge()
                self.mail.logout()
            except imaplib.IMAP4.error as e:
                print(f"⚠️ IMAP close error: {e}")
            except Exception as e:
                print(f"⚠️ Unexpected close error: {e}")