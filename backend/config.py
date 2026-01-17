import os
from dotenv import load_dotenv 

load_dotenv() 

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# 🚀 PURE GROQ CONFIGURATION
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Map Email Address -> Official Bank Name
BANK_REGISTRY = {
    # SBI
    'cbssbi.cas@alerts.sbi.co.in': 'SBI',
    'alerts@alerts.sbi.co.in': 'SBI',
    'no-reply@alerts.sbi.co.in': 'SBI',

    # HDFC
    'alerts@hdfcbank.net': 'HDFC',
    'no-reply@hdfcbank.net': 'HDFC',
    'alerts@alerts.hdfcbank.net': 'HDFC',

    # ICICI
    'alerts@icicibank.com': 'ICICI',
    'no-reply@icicibank.com': 'ICICI',

    # Axis
    'alerts@axisbank.com': 'Axis Bank',
    'no-reply@axisbank.com': 'Axis Bank',

    # Kotak
    'alerts@kotak.com': 'Kotak',
    'no-reply@kotak.com': 'Kotak',

    # Others
    'alerts@idfcfirstbank.com': 'IDFC First',
    'alerts@yesbank.in': 'Yes Bank',
}

# 🛑 IGNORE_SUBJECTS: 
# Only discard if the SUBJECT line contains these keywords.
IGNORE_SUBJECTS = {
    # Security / Auth
    'otp', 'one time password', 'verification code', 'auth code',
    'login alert', 'password change', 'pin change', 
    'biometric login', 'set up device', 'login pin',
    
    # Non-Financial / Marketing
    'welcome to', 'happy birthday', 'contact details update', 'kyc',
    'statement', 'summary for the month', 'customer advice',
    'personal loan', 'credit card offer', 'upgrade your card',
    
    # Failed Transactions
    'payment unsuccessful', 'transaction declined', 
    'transaction failed', 'returned'
}

# 🛑 IGNORE_BODY_PHRASES:
# Checked only in the first 500 characters of the body.
IGNORE_BODY_PHRASES = {
    'otp is', 'is your otp', 'verification code is',
    'e-mandate', 'mandate registration', 'registered for',
    'registration successful', 'auto-pay registered',
    'beneficiary added', 'login to', 'logged in', 'device registration'
}

# Categories the LLM is allowed to choose from
CATEGORY_LIST = [
    "Food & Dining",
    "Groceries",
    "Transportation",
    "Shopping",
    "Bills & Utilities",
    "Entertainment",
    "Health & Wellness",
    "Investment",
    "Transfer",
    "Income",     # Added for Salary/Dividends
    "Refund",     # Added for reversals
    "Uncategorized"
]