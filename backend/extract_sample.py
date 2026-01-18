import imaplib
import email
from email.header import decode_header
import os
import re
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# 1. Load Environment Variables
load_dotenv()

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
TARGET_SENDER = "alerts@hdfcbank.net"

# 2. 🛡️ Pre-flight Check
if not IMAP_USER or not IMAP_PASSWORD:
    print("❌ CRITICAL ERROR: Email Credentials missing.")
    print("   Please ensure you have a '.env' file with IMAP_USER and IMAP_PASSWORD.")
    exit(1)

def get_decoded_header(header_text):
    if not header_text: return ""
    try:
        decoded_list = decode_header(header_text)
        text = ""
        for bytes_data, encoding in decoded_list:
            if isinstance(bytes_data, bytes):
                text += bytes_data.decode(encoding or "utf-8", errors="ignore")
            else:
                text += str(bytes_data)
        return text.strip()
    except Exception:
        return str(header_text)

def normalize_subject(subject):
    if not subject: return "NO_SUBJECT"
    # Replace numbers with X to group similar templates
    return re.sub(r'\d+', 'X', subject)

def extract_unique_templates():
    try:
        print(f"🔌 Connecting to {IMAP_SERVER} as {IMAP_USER}...")
        
        # Connect
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("INBOX")

        print(f"🔍 Searching for all emails from: {TARGET_SENDER}")
        status, data = mail.search(None, f'(FROM "{TARGET_SENDER}")')
        
        if not data or not data[0]:
            print("❌ No emails found from this sender.")
            return

        email_ids = data[0].split()
        total_emails = len(email_ids)
        print(f"📂 Found {total_emails} emails. Starting full scan...")

        seen_templates = set()
        samples = []
        processed = 0

        # Scan Newest to Oldest
        for e_id in reversed(email_ids):
            
            # Progress Log every 50 emails
            processed += 1
            if processed % 50 == 0:
                print(f"   ⏳ Scanned {processed}/{total_emails} emails...")

            try:
                # Fetch Header
                _, msg_data = mail.fetch(e_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
                raw_header = msg_data[0][1]
                msg = email.message_from_bytes(raw_header)
                subject = get_decoded_header(msg["Subject"])

                # Check Uniqueness
                template_key = normalize_subject(subject)
                
                if template_key not in seen_templates:
                    print(f"   ✨ New Template Found: {subject[:40]}...")
                    
                    # Fetch Full Body
                    _, body_data = mail.fetch(e_id, '(RFC822)')
                    full_msg = email.message_from_bytes(body_data[0][1])
                    
                    body_text = "No Body Found"
                    
                    # Robust Body Extraction
                    if full_msg.is_multipart():
                        for part in full_msg.walk():
                            if part.get_content_type() == "text/html":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    soup = BeautifulSoup(payload, "html.parser")
                                    body_text = soup.get_text(separator=" ", strip=True)
                                    break
                    else:
                        payload = full_msg.get_payload(decode=True)
                        if payload:
                            if full_msg.get_content_type() == "text/html":
                                soup = BeautifulSoup(payload, "html.parser")
                                body_text = soup.get_text(separator=" ", strip=True)
                            else:
                                body_text = payload.decode(errors='ignore')

                    # Add to samples
                    clean_body = " ".join(body_text.split())
                    samples.append({
                        "subject": subject,
                        "body": clean_body
                    })
                    seen_templates.add(template_key)
            
            except Exception as e:
                # Don't crash on one bad email, just skip
                continue

        # Save to File
        if samples:
            with open("email_samples.txt", "w", encoding="utf-8") as f:
                for i, sample in enumerate(samples):
                    f.write(f"--- SAMPLE {i+1} ---\n")
                    f.write(f"SUBJECT: {sample['subject']}\n")
                    f.write(f"BODY: {sample['body']}\n")
                    f.write("\n" + "="*50 + "\n\n")
            print(f"✅ Full Scan Complete! Saved {len(samples)} unique templates to 'email_samples.txt'")
        else:
            print("⚠️ No unique samples found.")

        mail.logout()

    except KeyboardInterrupt:
        print("\n🛑 Scan stopped by user. Saving what we have...")
        # Save whatever we found before stopping
        if samples:
             with open("email_samples.txt", "w", encoding="utf-8") as f:
                for i, sample in enumerate(samples):
                    f.write(f"--- SAMPLE {i+1} ---\n")
                    f.write(f"SUBJECT: {sample['subject']}\n")
                    f.write(f"BODY: {sample['body']}\n")
                    f.write("\n" + "="*50 + "\n\n")

    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    extract_unique_templates()