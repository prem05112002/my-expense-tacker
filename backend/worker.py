import imaplib
import email
from email.header import decode_header
from datetime import datetime
import threading

from models import db, Transaction, User, CategoryRule
from smart_parser import HybridParser
from config import BANK_REGISTRY, IGNORE_SUBJECTS, IGNORE_BODY_PHRASES

class MailWorker:
    def __init__(self, app):
        self.app = app
        self.parser = HybridParser()

    def start_onboarding(self, user):
        thread = threading.Thread(target=self._fetch_and_process, args=(user.id,))
        thread.start()

    def _fetch_and_process(self, user_id):
        with self.app.app_context():
            user = User.query.get(user_id)
            if not user: return
            
            print(f"🔄 Syncing {user.imap_user}...")
            
            try:
                mail = imaplib.IMAP4_SSL(user.imap_server)
                mail.login(user.imap_user, user.imap_password)
                mail.select("inbox")

                # Load Watermarks
                high_watermark = user.last_processed_uid if user.last_processed_uid else 0
                low_watermark = user.min_processed_uid 
                
                # ==========================================================
                # 🚀 PHASE 1: FORWARD SYNC (Get Newest Emails)
                # ==========================================================
                if high_watermark > 0:
                    print(f"📡 Checking for NEW emails (UID > {high_watermark})...")
                    self._search_and_process(mail, user, f'{high_watermark + 1}:*', is_backfill=False)
                else:
                    print("🚀 First Run: Starting Initial Scan...")
                    self._search_and_process(mail, user, '1:*', is_backfill=False)

                # Reload User to get updated watermarks before Phase 2
                db.session.refresh(user)
                low_watermark = user.min_processed_uid

                # ==========================================================
                # 🕰️ PHASE 2: BACKFILL HISTORY (Get Older Emails)
                # ==========================================================
                if low_watermark is not None and low_watermark > 1:
                    print(f"📜 Backfilling History (UID < {low_watermark})...")
                    # We try to fetch a large chunk of history
                    self._search_and_process(mail, user, f'1:{low_watermark - 1}', is_backfill=True)
                elif low_watermark == 1:
                    print("✅ History Fully Synced.")

            except Exception as e:
                print(f"❌ Worker Error: {e}")

    def _search_and_process(self, mail, user, search_criterion, is_backfill=False):
        """
        Searches IMAP and processes ALL resulting UIDs.
        Updates User Progress (Watermarks) only AFTER the entire traversal.
        """
        status, data = mail.uid('search', None, search_criterion)
        if not data or not data[0]: return

        email_uids = data[0].split()
        if not email_uids: return

        # ⚡ ALWAYS process Newest -> Oldest
        email_uids.reverse()

        # ---------------------------------------------------------
        # 1. Filter UIDs (Strict Client-Side Check)
        # ---------------------------------------------------------
        filtered_uids = []
        current_min_db = user.min_processed_uid or float('inf')
        current_max_db = user.last_processed_uid or 0

        for uid_bytes in email_uids:
            uid = int(uid_bytes.decode())
            if is_backfill:
                if uid < current_min_db: filtered_uids.append(uid_bytes)
            else:
                if uid > current_max_db: filtered_uids.append(uid_bytes)

        if not filtered_uids:
            # If server returned garbage (e.g., we asked for <100 but got 105),
            # and we filtered everything out, we must manually move the pointer
            # to prevent an infinite loop.
            if is_backfill and user.min_processed_uid:
                print("⚠️ No valid UIDs in range. Forcing history pointer down...")
                user.min_processed_uid = max(1, user.min_processed_uid - 50)
                db.session.commit()
            return

        total_to_scan = len(filtered_uids)
        print(f"📂 Processing {total_to_scan} emails in this run...")

        # ---------------------------------------------------------
        # 2. Traversal Loop (Chunks of 20 to manage memory)
        # ---------------------------------------------------------
        CHUNK_SIZE = 20
        
        # Trackers for the FINAL update
        session_min_uid = float('inf')
        session_max_uid = 0
        
        # Cache existing IDs to avoid DB hits
        existing_uids = set(
            t.email_id for t in Transaction.query.with_entities(Transaction.email_id).filter_by(user_id=user.id).all()
        )

        for i in range(0, total_to_scan, CHUNK_SIZE):
            chunk = filtered_uids[i : i + CHUNK_SIZE]
            
            for uid_bytes in chunk:
                uid_str = uid_bytes.decode()
                uid_int = int(uid_str)

                # Update Local Trackers
                if uid_int < session_min_uid: session_min_uid = uid_int
                if uid_int > session_max_uid: session_max_uid = uid_int

                if uid_str in existing_uids: continue

                try:
                    # Fetch Headers
                    _, msg_data = mail.uid('fetch', uid_bytes, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])')
                    if not msg_data or not msg_data[0]: continue
                    
                    msg = email.message_from_bytes(msg_data[0][1])
                    sender = self._extract_email(msg.get("From"))
                    
                    if sender in BANK_REGISTRY:
                        subj = self._decode_header(msg.get("Subject")).lower()
                        if not any(k in subj for k in IGNORE_SUBJECTS):
                            print(f"✅ Scanning: {BANK_REGISTRY[sender]} (UID {uid_str})")
                            self._fetch_full_body_and_save(mail, uid_bytes, user.id, uid_str, BANK_REGISTRY[sender])
                except Exception:
                    continue

            # 💾 Commit TRANSACTIONS every chunk (so we don't lose data on crash)
            # Note: We do NOT commit the User Watermarks yet.
            try:
                db.session.commit()
            except:
                db.session.rollback()

        # ---------------------------------------------------------
        # 3. Traversal Complete: UPDATE USER WATERMARKS
        # ---------------------------------------------------------
        # We only update the pointers if we actually saw UIDs
        if session_max_uid > 0:
            updated = False
            
            # Forward Sync: Update Max
            if not is_backfill:
                if session_max_uid > (user.last_processed_uid or 0):
                    user.last_processed_uid = session_max_uid
                    updated = True
                # First run init
                if user.min_processed_uid is None:
                    user.min_processed_uid = session_min_uid
                    updated = True

            # Backfill: Update Min
            if is_backfill:
                current_min = user.min_processed_uid or float('inf')
                # We successfully scanned down to session_min_uid. 
                # Next time start below that.
                if session_min_uid < current_min:
                    user.min_processed_uid = session_min_uid
                    updated = True
                else:
                    # Fallback if gaps exist
                    user.min_processed_uid = current_min - 1
                    updated = True

            if updated:
                db.session.commit()
                print(f"📌 Sync Complete. Watermarks updated: Max={user.last_processed_uid}, Min={user.min_processed_uid}")

    def _fetch_full_body_and_save(self, mail_conn, uid_bytes, user_id, e_id_str, bank_name):
        _, msg_data = mail_conn.uid('fetch', uid_bytes, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    body = part.get_payload(decode=True).decode(errors='ignore')
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors='ignore')

        clean_text = self.parser._clean_html(body).lower()[:500]
        if any(phrase in clean_text for phrase in IGNORE_BODY_PHRASES):
            return 
            
        email_data = {"sender": self._extract_email(msg.get("From")), "body": body}
        result = self.parser.parse_email(user_id, email_data)
        
        if result:
            result['date'] = self._normalize_date(result.get('date'))
            self._save_transaction(user_id, result, e_id_str, bank_name)

    def _normalize_date(self, date_val):
        if isinstance(date_val, datetime): return date_val
        if not date_val: return datetime.now()
        text = str(date_val).strip()
        formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"]
        for fmt in formats:
            try: return datetime.strptime(text, fmt)
            except ValueError: continue
        return datetime.now() 

    def _apply_learning(self, merchant, predicted_category):
        rule = CategoryRule.query.filter(CategoryRule.merchant_pattern.ilike(f"%{merchant}%")).first()
        return rule.preferred_category if rule else predicted_category

    def _check_duplicate_status(self, user_id, data):
        ref_no = data.get('ref_number')
        if ref_no and str(ref_no).lower() not in ['null', 'none', '', 'n/a']:
            exists = Transaction.query.filter_by(user_id=user_id, ref_number=ref_no).first()
            if exists: return 'HARD_DUPLICATE'
        
        if data.get('amount') is not None:
            potential_dupe = Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.amount == data['amount'],
                Transaction.merchant == data['merchant'],
                Transaction.date == data['date']
            ).first()
            if potential_dupe: return 'SOFT_DUPLICATE'
        return 'NEW'

    def _save_transaction(self, user_id, data, unique_email_id, bank_name):
        try:
            clean_merchant = self.parser._clean_merchant_name(data.get('merchant', 'Unknown'))
            transaction_type = data.get('type', 'DEBIT').upper()
            
            tx_status = "CLEAN" if data.get('amount') is not None else "PENDING"
            
            dup_status = self._check_duplicate_status(user_id, data)
            if dup_status == 'HARD_DUPLICATE': return
            is_flagged = (dup_status == 'SOFT_DUPLICATE')
            
            final_category = "Uncategorized"
            if tx_status == "CLEAN":
                final_category = self._apply_learning(clean_merchant, data.get('category', 'Uncategorized'))

            new_tx = Transaction(
                user_id=user_id,
                amount=data.get('amount'),
                merchant=clean_merchant,
                date=data['date'],
                ref_number=data.get('ref_number'),
                email_id=unique_email_id,
                category=final_category,
                bank_name=bank_name,
                tx_type=transaction_type,
                status=tx_status, 
                is_potential_duplicate=is_flagged 
            )
            # Add to session, but do NOT commit yet (we commit in the loop in batches)
            db.session.add(new_tx)
            # We flush to get an ID/check constraints without closing the transaction
            db.session.flush() 
            print(f"💾 SAVED: {clean_merchant} ({tx_status})")
        except Exception as e:
            # We don't rollback the whole session here, just skip this one item
            print(f"❌ DB Save Error: {e}")

    def _extract_email(self, sender_str):
        if not sender_str: return ""
        return sender_str.split("<")[1].strip(">") if "<" in sender_str else sender_str.strip()

    def _decode_header(self, header_text):
        if not header_text: return ""
        decoded_list = decode_header(header_text)
        text = ""
        for bytes_data, encoding in decoded_list:
            if isinstance(bytes_data, bytes):
                text += bytes_data.decode(encoding or "utf-8", errors="ignore")
            else:
                text += str(bytes_data)
        return text