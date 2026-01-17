from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    
    # Credentials
    imap_server = Column(String, default="imap.gmail.com")
    imap_user = Column(String)
    imap_password = Column(String) # In production, this should be encrypted
    
    # Sync Markers
    last_processed_uid = Column(Integer, default=0)
    min_processed_uid = Column(Integer, default=None, nullable=True)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    amount = Column(Float)
    merchant = Column(String)
    category = Column(String)
    date = Column(DateTime)
    
    # Audit details
    ref_number = Column(String, nullable=True)
    email_id = Column(String) # The UID from the email
    bank_name = Column(String)
    
    # Internal status
    tx_type = Column(String) # DEBIT/CREDIT
    status = Column(String, default="CLEAN") 
    is_potential_duplicate = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

class CategoryRule(Base):
    __tablename__ = "category_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    merchant_pattern = Column(String)
    preferred_category = Column(String)