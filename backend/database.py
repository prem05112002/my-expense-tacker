# backend/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

# ✅ IMPORT from your sibling file
from setup_db import DATABASE_URL, bootstrap_database

# 1. Create Engine
engine = create_engine(DATABASE_URL)

# 2. Connection Logic with Auto-Heal
try:
    # Try to connect purely to check if DB exists
    with engine.connect() as connection:
        print(f"🚀 Connected to database: {DATABASE_URL.split('/')[-1]}")
        
except OperationalError:
    # 3. If it fails, call the bootstrap function from the other file
    bootstrap_database()
    
    # 4. Re-create the engine now that the DB exists
    engine = create_engine(DATABASE_URL)

# 5. Standard Setup
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()