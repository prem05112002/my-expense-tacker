from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import sync_service

# Initialize DB and Tables
models.init_db()  # <--- Triggers DB & Table creation

app = FastAPI()

# Enable CORS (so your local React/Vue app can hit this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINTS ---

@app.post("/sync")
def trigger_sync(db: Session = Depends(models.get_db)):
    """Button press: Go fetch new emails"""
    return sync_service.fetch_and_sync_transactions(db)

@app.get("/transactions")
def read_transactions(
    category: Optional[str] = None, 
    limit: int = 50, 
    db: Session = Depends(models.get_db)
):
    """Get list for Dashboard Table"""
    query = db.query(models.Transaction)
    if category:
        query = query.filter(models.Transaction.category == category)
    
    return query.order_by(models.Transaction.date.desc()).limit(limit).all()

@app.get("/dashboard/summary")
def get_summary(db: Session = Depends(models.get_db)):
    """Get data for Pie Charts / Total Cards"""
    # Simple aggregation logic
    total_spent = 0
    cat_summary = {}
    
    txs = db.query(models.Transaction).filter(models.Transaction.type == "DEBIT").all()
    for t in txs:
        total_spent += t.amount
        cat_summary[t.category] = cat_summary.get(t.category, 0) + t.amount
        
    return {
        "total_spent": total_spent,
        "category_breakdown": cat_summary
    }