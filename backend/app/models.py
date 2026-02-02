from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from .database import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    color = Column(String, default="#94a3b8")
    is_income = Column(Boolean, default=False)
    transactions = relationship("Transaction", back_populates="category")
    rules = relationship("TransactionRule", back_populates="category") 

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

class TransactionRule(Base):
    __tablename__ = "transaction_rules"

    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String, index=True)  # e.g. "SWIGGY"
    new_merchant_name = Column(String)    # e.g. "Swiggy"
    match_type = Column(String, default="CONTAINS") # CONTAINS, EXACT, STARTS_WITH
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category", back_populates="rules")

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
    ignored_categories = Column(String, default="") 
    income_categories = Column(String, default="Salary,Income") 
    view_cycle_offset = Column(Integer, default=0)

class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id = Column(Integer, primary_key=True, index=True)
    merchant_name = Column(String, index=True)
    amount = Column(Float)
    frequency = Column(String)  # "MONTHLY", "YEARLY", "WEEKLY", "IRREGULAR"
    next_due_date = Column(Date)
    
    # We link it to the specific transaction that triggered it, if needed
    last_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)