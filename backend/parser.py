import re
from datetime import datetime
from bs4 import BeautifulSoup

class HDFCParser:
    def parse(self, html_body, subject):
        # 1. Clean HTML
        # Remove HTML tags and normalize whitespace to single spaces
        soup = BeautifulSoup(html_body, "html.parser")
        text = " ".join(soup.get_text(separator=" ", strip=True).split())
        
        # Normalize subject for loose matching (remove spaces, lowercase)
        strict_subject = "".join(subject.split()).lower()

        # 2. Universal Reference Number Extraction (Works across all templates)
        ref_match = re.search(r'(?:Reference\s*number\s*is|Ref\s*No|UPI\s*Ref\s*No)\s*[:\-]?\s*(\d+)', text, re.IGNORECASE)
        ref_number = ref_match.group(1) if ref_match else None

        # =========================================================
        # CASE 1: UPI OUTGOING (Sample 1)
        # Context: Money leaving account via UPI
        # =========================================================
        if "youhavedoneaupitxn" in strict_subject:
            pattern = (
                r"Rs\.?\s*([\d,.]+)"                # 1. AMOUNT
                r"\s*has\s*been\s*"
                r"(debited|credited)"               # 2. TYPE (Capture "debited")
                r"\s*from\s*account\s*"
                r"(\d{4})"                          # 3. ACC_NUM
                r"\s*to\s*VPA\s*"
                r"([^\s@]+)"                        # 4. UPI ID (Before @)
                r"@"
                r"([^\s]+)"                         # 5. BANK ID (Stops at space)
                r"\s+"
                r"(.*?)"                            # 6. MERCHANT NAME
                r"\s*on\s*"
                r"([\d\w\s,./-]+?)"                 # 7. DATE
                r"(?:\.|$)"                         # Stop at dot
            )
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._package(
                    amount=match.group(1),
                    raw_type=match.group(2),
                    acc_card=match.group(3),
                    merchant=match.group(6),
                    bank_id=match.group(5),
                    upi_id=match.group(4),
                    date_str=match.group(7),
                    category="UPI",
                    ref=ref_number
                )

        # =========================================================
        # CASE 2: UPI INCOMING (Sample 2)
        # Context: Money coming into account via UPI
        # =========================================================
        elif "view:accountupdate" in strict_subject:
            pattern = (
                r"Rs\.?\s*([\d,.]+)"                # 1. AMOUNT
                r"\s*is\s*successfully\s*"
                r"(debited|credited)"               # 2. TYPE
                r"\s*to\s*your\s*account\s*\**"
                r"(\d{4})"                          # 3. ACC_NUM
                r"\s*by\s*VPA\s*"
                r"([^\s@]+)"                        # 4. UPI ID
                r"@"
                r"([^\s]+)"                         # 5. BANK ID
                r"\s+"
                r"(.*?)"                            # 6. MERCHANT NAME
                r"\s*on\s*"
                r"([\d\w\s,./-]+?)"                 # 7. DATE
                r"(?:\.|$)"
            )
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._package(
                    amount=match.group(1),
                    raw_type=match.group(2),
                    acc_card=match.group(3),
                    merchant=match.group(6),
                    bank_id=match.group(5),
                    upi_id=match.group(4),
                    date_str=match.group(7),
                    category="UPI",
                    ref=ref_number
                )

        # =========================================================
        # CASE 3: DEBIT CARD (Sample 3)
        # Context: Swiping card / Online usage
        # =========================================================
        elif "debitedviadebitcard" in strict_subject:
            pattern = (
                r"Rs\.?\s*([\d,.]+)"                # 1. AMOUNT
                r"\s*is\s*"
                r"(debited|credited)"               # 2. TYPE
                r"\s*from\s*your\s*HDFC\s*Bank\s*Debit\s*Card\s*ending\s*"
                r"(\d{4})"                          # 3. CARD NUM
                r"\s*at\s*"
                r"(.*?)"                            # 4. MERCHANT
                r"\s*on\s*"
                r"([\d\w\s,./-]+?)"                 # 5. DATE
                r"\s*at\s*"
            )
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._package(
                    amount=match.group(1),
                    raw_type=match.group(2),
                    acc_card=match.group(3),
                    merchant=match.group(4),
                    bank_id="HDFC",
                    upi_id=None,
                    date_str=match.group(5),
                    category="CARD_SPEND",
                    ref=ref_number
                )

        # =========================================================
        # CASE 4: NEFT / DEPOSIT (Sample 4) - FIXED
        # Context: Salary / NEFT / IMPS Incoming
        # =========================================================
        elif "newdepositalert" in strict_subject:
            pattern = (
                r"The\s*amount\s*"
                # FIX: [a-zA-Z/]+ captures "credited/received" as one token
                r"([a-zA-Z/]+)"                     # 1. TYPE 
                r"\s*is\s*INR\s*"
                r"([\d,.]+)"                        # 2. AMOUNT
                r"\s*in\s*your\s*account\s*(?:XX)*"
                r"(\d{4})"                          # 3. ACC_NUM
                r"\s*on\s*"
                r"([\d\w\s,./-]+?)"                 # 4. DATE
                r"\s*on\s*account\s*of\s*NEFT\s*"
                r"(.*?)"                            # 5. MERCHANT
                r"\s*Your\s*A/c"
            )
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._package(
                    amount=match.group(2),          # Note: Amount is now Group 2
                    raw_type=match.group(1),        # Type is Group 1
                    acc_card=match.group(3),
                    merchant=match.group(5),
                    bank_id="NEFT",
                    upi_id=None,
                    date_str=match.group(4),
                    category="DEPOSIT",
                    ref=ref_number
                )

        return None

    # --- HELPERS ---

    def _package(self, amount, raw_type, acc_card, merchant, bank_id, upi_id, date_str, category, ref):
        # 1. Determine Type (Debit vs Credit)
        tx_type = "DEBIT"
        rt = raw_type.lower()
        if "credit" in rt or "receive" in rt:
            tx_type = "CREDIT"
        
        # 2. Clean Amount
        try:
            clean_amt = float(amount.replace(",", ""))
        except:
            clean_amt = 0.0

        # 3. Clean Merchant String
        # Removes prefixes like "Cr-", "Dr-", "NEFT"
        clean_merch = merchant.strip() if merchant else "Unknown"
        clean_merch = re.sub(r'^(?:Cr|Dr|NEFT|IMPS|ACH)-?', '', clean_merch, flags=re.IGNORECASE).strip()

        return {
            "amount": clean_amt,
            "type": tx_type,
            "category": category,
            "merchant": clean_merch.title(),
            "bank_id": bank_id,
            "upi_id": upi_id,
            "acc_card_last4": acc_card,
            "date": self._parse_date(date_str),
            "ref_number": ref
        }

    def _parse_date(self, date_str):
        if not date_str: return datetime.now()
        
        # Normalize: replace separators with space, title case for Months
        clean = re.sub(r'[,.]', ' ', date_str).strip().title()
        clean = " ".join(clean.split())
        clean_normalized = clean.replace("-", " ").replace("/", " ")

        formats = [
            "%d %m %Y",      # 18 01 2026
            "%d %m %y",      # 18 01 26
            "%d %b %Y",      # 26 Dec 2025
            "%d %b %y",      # 25 Jul 25
            "%d %B %Y",      # 26 December 2025
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(clean_normalized, fmt)
            except ValueError:
                continue
        return datetime.now()