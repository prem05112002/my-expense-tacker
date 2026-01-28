import re
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from bs4 import BeautifulSoup

@dataclass
class Transaction:
    bank_name: str
    amount: float
    payment_type: str
    account_num: int
    payment_mode: str
    date: str
    upi_id: Optional[str] = None
    merchant_name: Optional[str] = None
    upi_transaction_id: Optional[str] = None
    # ✅ NEW FIELD
    category_id: Optional[int] = None

# --- REGEX PATTERNS (Same as before) ---
PATTERNS = {
    "UPI_DEBIT": {
        "regex": r"HDFC BANK Dear (Dear\s+)?Customer,(Dear Customer,)* Rs.(\s)*([0-9,.]+) has been (debited) from account (\*?\*?)?(\d{4}) to VPA ([^@]+@[^@]+) on (\d{1,2}-\d{1,2}-\d{2,4}). Your UPI transaction reference number is (\d+)\.?(.*)",
        "mode": "UPI",
        "map": {"amount": 4, "type_grp": 5, "acc": 7, "vpa": 8, "date": 9, "ref": 10}
    },
    "DEBIT_CARD_POS": {
        "regex": r"HDFC BANK Dear Card(\s)*(Holder|Member), Thank you for using your HDFC Bank (Debit) Card ending (\d{4}) for Rs(\s)*([0-9,.]+) at (.+) on (\d{1,2}-\d{1,2}-\d{2,4}) (.*)",
        "mode": "CARD",
        "map": {"type_grp": 3, "acc": 4, "amount": 6, "merch": 7, "date": 8}
    },
    "YOUTUBE_AUTOPAY": {
        "regex": r"HDFC BANK (Youtube bill payment confirmation Dear Customer, Your YouTube bill set on e-Mandate is (paid) through your HDFC Bank Debit Card. Current Txn Amt: INR.|Dear Customer, Greetings from HDFC Bank! Your Youtube bill, set up through E-mandate \(Auto payment\), has been successfully (paid) using your HDFC Bank Debit Card ending \d{4}. Transaction Details: Amount: INR)\s*([0-9,.]+) Date:\s*(\d{1,2}/\d{1,2}/\d{2,4}) SI (hub|Hub) ID(.*)",
        "mode": "CARD",
        "map": {"type_grp": [2, 3], "amount": 4, "date": 5, "merch_static": "YouTube"}
    },
    "UPI_CREDIT": {
        "regex": r"HDFC BANK Dear (Dear\s+)?Customer,(Dear Customer,)* Rs.(\s)*([0-9,.]+) is successfully (credited) to your account (\*?\*?)?(\d{4}) by VPA ([^@]+@[^@]+) on (\d{1,2}-\d{1,2}-\d{2,4}). Your UPI transaction reference number is (\d+)\.?(.*)",
        "mode": "UPI",
        "map": {"amount": 4, "type_grp": 5, "acc": 7, "vpa": 8, "date": 9, "ref": 10}
    },
    "NEFT_CREDIT": {
        "regex": r"HDFC BANK Dear Customer, You have received a credit in your account. Here are the details The amount (credited/received) is INR(\s)*([0-9,.]+) in your account xx(\d{4}) on (\d{1,2}-[A-Z]{3}-\d{4}) on account of NEFT (.*) Your A/c is (.*)",
        "mode": "NETBANKING",
        "map": {"type_grp": 1, "amount": 3, "acc": 4, "date": 5, "merch": 6}
    },
    "CARD_DEBIT_GENERAL": {
        "regex": r"HDFC BANK Dear Customer, Greetings from HDFC Bank! Rs.(\s)*([0-9,.]+) is (debited) from your HDFC Bank Debit Card ending (\d{4}) at (.*) on (\d{1,2}\s+[A-Z][a-z]{2,9},\s+\d{4}) at (.*)",
        "mode": "CARD",
        "map": {"amount": 2, "type_grp": 3, "acc": 4, "merch": 5, "date": 6}
    },
    "NEFT_CREDIT_ALT": {
        "regex": r"HDFC BANK Dear Customer, Greetings from HDFC Bank! Rs.INR(\s)*([0-9,.]+) has been successfully (credited|added) to your account ending XX(\d{4}) (by|from) NEFT (.*) on (\d{1,2}-[A-Z]{3}-\d{4})\.(.*)",
        "mode": "NETBANKING",
        "map": {"amount": 2, "type_grp": 3, "acc": 4, "merch": 6, "date": 7}
    },
    "NETBANKING_DEBIT": {
        "regex": r"HDFC BANK Dear Customer, This is to inform you that an amount of Rs.(\s)*([0-9,.]+) has been (debited) from your account No. XXXX(\d{4}) on account of (.*)",
        "mode": "NETBANKING",
        "map": {"amount": 2, "type_grp": 3, "acc": 4, "merch": 5}
    },
    "DIRECT_ACC": {
        "regex": r"HDFC BANK Dear (Dear\s+)?Customer, Amount of INR(\s)*([0-9,.]+) has been (credited|debited) (to|from) A/c XX(\d{4}) at (.*)",
        "mode": "DEPOSIT",
        "map": {"amount": 3, "type_grp": 4, "acc": 6, "merch": 7}
    },
    "NETBANKING_PAYMENT": {
        "regex": r"HDFC BANK Dear Customer, Thank you for using HDFC Bank NetBanking for (payment) of Rs.(\s)*([0-9,.]+) from A/c XXXX(\d{4}) to (.*) For more details on the (.*)",
        "mode": "NETBANKING",
        "map": {"type_grp": 1, "amount": 3, "acc": 4, "merch": 5}
    },
    "WITHDRAWAL": {
        "regex": r"HDFC BANK Dear Card (Holder|Member), Thank you for using your HDFC Bank Debit Card ending (\d{4}) for ATM (withdrawal) for Rs(\s)*([0-9,.]+) in (.*) on (\d{1,2}-\d{1,2}-\d{2,4}) (.*)",
        "mode": "WITHDRAWAL",
        "map": {"acc": 2, "type_grp": 3, "amount": 5, "merch": 6, "date": 7}
    }
}

# --- HELPERS ---
def clean_text(text: str) -> str:
    if not text: return ""
    soup = BeautifulSoup(text, "html.parser")
    return " ".join(soup.get_text(separator=" ").split())

def parse_date(date_str: str) -> Optional[str]:
    """
    Standardizes various date formats to YYYY-MM-DD.
    """
    if not date_str: return None
    
    # Clean whitespace and convert to Title Case (handles 'JAN' vs 'Jan')
    date_str = date_str.strip().title()
    
    formats = [
        "%d-%m-%y",    # 25-12-25
        "%d-%m-%Y",    # 25-12-2025
        "%d/%m/%y",    # 25/12/25
        "%d/%m/%Y",    # 25/12/2025
        "%d-%b-%Y",    # 23-Jan-2026 (Abbreviated, Hyphen)
        "%d-%b-%y",    # 23-Jan-26   (Abbreviated, Hyphen)
        "%d %B, %Y",   # 12 January, 2025 (Full Month, Comma)
        "%d %b, %Y",   # 26 Dec, 2025 (Abbreviated, Comma) <--- ADDED THIS
        "%d %b %Y"     # 26 Dec 2025 (Abbreviated, No Comma) <--- ADDED THIS
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
            
    return None

def determine_type(action_verb: str) -> str:
    if not action_verb: return "debit"
    action = action_verb.lower().strip()
    if any(x in action for x in ['debited', 'paid', 'payment', 'withdrawal', 'debit']): return "debit"
    if any(x in action for x in ['credited', 'received', 'added', 'credit']): return "credit"
    return "debit"

def extract_metadata(body: str) -> Optional[Transaction]:
    for name, config in PATTERNS.items():
        pattern = re.compile(config['regex'], re.IGNORECASE | re.DOTALL)
        match = pattern.search(body)
        if match:
            mapping = config['map']
            try:
                # Amount
                amt = float(match.group(mapping.get('amount', -1)).replace(',', ''))
                
                # Account
                acc_grp = mapping.get('acc')
                acc = int(match.group(acc_grp)) if acc_grp else 0
                
                # Payment Type
                type_input = mapping.get('type_grp')
                action_verb = None
                if isinstance(type_input, list):
                    for grp in type_input:
                        if match.group(grp): 
                            action_verb = match.group(grp)
                            break
                else:
                    action_verb = match.group(type_input)
                p_type = determine_type(action_verb)

                # Merchant / VPA Logic
                merch, upi_id = None, None
                if 'vpa' in mapping:
                    raw_vpa = match.group(mapping['vpa']).strip()
                    parts = raw_vpa.split(' ')
                    upi_id = parts[0]
                    merch = " ".join(parts[1:]) if len(parts) > 1 else upi_id
                elif 'merch' in mapping:
                    merch = match.group(mapping['merch']).strip()
                elif 'merch_static' in mapping:
                    merch = mapping['merch_static']

                # Date (Standardized)
                date_str = None
                if 'date' in mapping:
                    date_str = parse_date(match.group(mapping['date']))

                # Ref
                ref = match.group(mapping['ref']).strip() if 'ref' in mapping else None

                return Transaction(
                    bank_name="HDFC Bank", amount=amt, payment_type=p_type,
                    account_num=acc, payment_mode=config['mode'], 
                    date=date_str, upi_id=upi_id, merchant_name=merch, 
                    upi_transaction_id=ref
                )
            except Exception as e:
                print(f"⚠️ Regex Match found but extraction failed for {name}: {e}")
                return None
    return None