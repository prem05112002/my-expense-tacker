from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from .database import Base

# ==========================
# 1. CATEGORY MODEL
# ==========================
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    color = Column(String, default="#94a3b8")
    is_income = Column(Boolean, default=False)

    # Relationships
    transactions = relationship("Transaction", back_populates="category")
    
    # ✅ FIX: This expects the class below to be named 'TransactionRule'
    rules = relationship("TransactionRule", back_populates="category") 

# ==========================
# 2. TRANSACTION MODEL
# ==========================
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    merchant_name = Column(String, index=True)
    amount = Column(Float)
    txn_date = Column(Date)
    payment_mode = Column(String)  # UPI, CARD, NETBANKING
    payment_type = Column(String)  # DEBIT, CREDIT
    bank_name = Column(String, nullable=True)
    upi_transaction_id = Column(String, nullable=True, index=True)
    
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="transactions")

# ==========================
# 3. RULE ENGINE MODEL (Renamed from CategoryRule)
# ==========================
class TransactionRule(Base):  # ✅ Renamed from CategoryRule to TransactionRule
    __tablename__ = "transaction_rules"

    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String, index=True)  # e.g. "SWIGGY"
    new_merchant_name = Column(String)    # e.g. "Swiggy"
    match_type = Column(String, default="CONTAINS") # CONTAINS, EXACT, STARTS_WITH
    
    category_id = Column(Integer, ForeignKey("categories.id"))
    
    # ✅ FIX: Links back to Category.rules
    category = relationship("Category", back_populates="rules")

# ==========================
# 4. OTHER MODELS
# ==========================
class StagingTransaction(Base):
    __tablename__ = "unmatched_emails"

    id = Column(Integer, primary_key=True, index=True)
    email_uid = Column(String, unique=True, index=True)
    email_subject = Column(String)
    email_body = Column(Text)
    received_at = Column(DateTime)

class IgnoredDuplicate(Base):
    __tablename__ = "ignored_duplicates"

    id = Column(Integer, primary_key=True, index=True)
    txn1_id = Column(Integer, index=True)
    txn2_id = Column(Integer, index=True)

class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    salary_day = Column(Integer, default=1) 
    monthly_budget = Column(Float, default=50000.0)
    budget_type = Column(String, default="FIXED") # FIXED or PERCENTAGE
    budget_value = Column(Float, default=50000.0)