from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from .database import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    color = Column(String, default="#94a3b8")

    transactions = relationship("Transaction", back_populates="category")
    rules = relationship("CategoryRule", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    txn_date = Column(Date, index=True)
    merchant_name = Column(String, index=True)
    amount = Column(Float)
    payment_mode = Column(String, index=True) # UPI, Card
    payment_type = Column(String, default="DEBIT") # CREDIT / DEBIT
    bank_name = Column(String, nullable=True)
    upi_transaction_id = Column(String, nullable=True, index=True)
    
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="transactions")

class CategoryRule(Base):
    __tablename__ = "category_rules"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, unique=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    
    category = relationship("Category", back_populates="rules")

class IgnoredDuplicate(Base):
    __tablename__ = "ignored_duplicates"

    id = Column(Integer, primary_key=True, index=True)
    txn1_id = Column(Integer, ForeignKey("transactions.id"), index=True) # The smaller ID
    txn2_id = Column(Integer, ForeignKey("transactions.id"), index=True) # The larger ID

class StagingTransaction(Base):
    __tablename__ = "unmatched_emails"

    id = Column(Integer, primary_key=True, index=True)
    email_uid = Column(String, unique=True, index=True)
    email_subject = Column(String)
    email_body = Column(Text, nullable=True)
    received_at = Column(DateTime)