import imaplib
import email
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from models import Transaction
from parser import HDFCParser

load_dotenv()

IMAP_SERVER = "imap.gmail.com"
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

def fetch_and_sync_transactions(db: Session):
    parser = HDFCParser()
    
    try:
        # Connect
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("INBOX")
        
        # Search HDFC Alerts only
        status, data = mail.search(None, '(FROM "alerts@hdfcbank.net")')
        email_ids = data[0].split()
        
        # Look at last 20 emails only (to be fast)
        recent_ids = email_ids[-20:] 
        
        added_count = 0
        
        for e_id in reversed(recent_ids):
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            subject = msg["Subject"]
            
            # Extract Body
            if msg.is_multipart():
                body = next((part.get_payload(decode=True).decode() for part in msg.walk() if part.get_content_type() == "text/html"), "")
            else:
                body = msg.get_payload(decode=True).decode()

            # Parse
            tx_data = parser.parse(body, subject)
            
            if tx_data:
                # Check Duplicate
                exists = db.query(Transaction).filter(Transaction.ref_number == tx_data['ref_number']).first()
                if not exists:
                    new_tx = Transaction(**tx_data)
                    db.add(new_tx)
                    added_count += 1
        
        db.commit()
        mail.logout()
        return {"status": "success", "new_transactions": added_count}

    except Exception as e:
        return {"status": "error", "message": str(e)}