# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    imap_server = db.Column(db.String(120))
    imap_user = db.Column(db.String(120))
    imap_password = db.Column(db.String(120))
    
    # ⬆️ PHASE 1: Tracks the NEWEST email we have seen (Forward Sync)
    last_processed_uid = db.Column(db.Integer, default=0)
    
    # ⬇️ PHASE 2: Tracks the OLDEST email we have seen (Backfill History)
    min_processed_uid = db.Column(db.Integer, nullable=True) 

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=True) 
    merchant = db.Column(db.String(200))
    date = db.Column(db.DateTime)
    category = db.Column(db.String(50), default="Uncategorized")
    tx_type = db.Column(db.String(10)) 
    bank_name = db.Column(db.String(50)) 
    ref_number = db.Column(db.String(100), nullable=True)
    is_potential_duplicate = db.Column(db.Boolean, default=False)
    email_id = db.Column(db.String(200), unique=True)
    status = db.Column(db.String(20), default="CLEAN")
    
class CategoryRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    merchant_pattern = db.Column(db.String(200), nullable=False)
    preferred_category = db.Column(db.String(50), nullable=False)