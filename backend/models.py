from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database # <--- NEW IMPORT
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Get the URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Create Engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime)
    amount = Column(Float)
    merchant = Column(String)     
    category = Column(String)     
    type = Column(String)         
    ref_number = Column(String, unique=True, index=True) 
    raw_subject = Column(String, nullable=True)

# 3. Automation Function
def init_db():
    """
    Checks if database exists. If not, creates it.
    Then creates all tables.
    """
    try:
        if not database_exists(engine.url):
            create_database(engine.url)
            print(f"✅ Database created at {engine.url}")
        else:
            print("ℹ️  Database already exists.")

        # Create Tables (This is safe to run multiple times)
        Base.metadata.create_all(bind=engine)
        print("✅ Tables initialized.")
        
    except Exception as e:
        print(f"❌ Error initializing DB: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()