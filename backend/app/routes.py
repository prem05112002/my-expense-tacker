from fastapi import APIRouter, HTTPException
from .database import get_db_connection
from .models import DashboardStats, Transaction, CategorizeRequest
from psycopg2.extras import RealDictCursor
from typing import List

router = APIRouter()

# --- 1. DASHBOARD OVERVIEW ---
@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats():
    conn = get_db_connection()
    if not conn: raise HTTPException(500, "DB Connection Failed")
    
    # Use RealDictCursor to get results as Dictionaries (easier for JSON)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # A. Total Spend
        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions")
        total_spend = cursor.fetchone()['total']
        
        # B. Uncategorized Count
        cursor.execute("""
            SELECT COUNT(*) as count FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE c.name = 'Uncategorized' OR t.category_id IS NULL
        """)
        uncategorized_count = cursor.fetchone()['count']
        
        # C. Recent Transactions (Last 5)
        cursor.execute("""
            SELECT t.*, c.name as category_name, c.color as category_color 
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            ORDER BY txn_date DESC LIMIT 5
        """)
        recent_txns = cursor.fetchall()

        # D. Category Breakdown (For Charts)
        cursor.execute("""
            SELECT c.name, SUM(t.amount) as value, c.color as fill
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            GROUP BY c.name, c.color
        """)
        breakdown = cursor.fetchall()
        
        return {
            "total_spend": total_spend,
            "uncategorized_count": uncategorized_count,
            "recent_transactions": recent_txns,
            "category_breakdown": breakdown
        }
    finally:
        conn.close()

# --- 2. TRANSACTION LIST ---
@router.get("/transactions", response_model=List[Transaction])
def get_transactions(limit: int = 50, offset: int = 0):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT t.*, c.name as category_name, c.color as category_color 
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            ORDER BY txn_date DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return cursor.fetchall()
    finally:
        conn.close()

# --- 3. SMART CATEGORIZATION (The Magic) ---
@router.post("/categorize")
def categorize_transaction(req: CategorizeRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Update the specific transaction(s) selected by user
        cursor.execute("""
            UPDATE transactions SET category_id = %s WHERE id = ANY(%s)
        """, (req.category_id, req.transaction_ids))
        
        # Step 2: Handle "Remember this rule"
        if req.create_rule and req.rule_keyword:
            # Check if rule already exists to avoid errors
            cursor.execute("SELECT 1 FROM category_rules WHERE keyword = %s", (req.rule_keyword,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO category_rules (keyword, category_id) VALUES (%s, %s)
                """, (req.rule_keyword, req.category_id))
            
            # Step 3: Handle "Apply to previous transactions"
            if req.apply_retroactive:
                # Update ALL transactions where merchant name matches the keyword
                # AND it isn't already categorized as this category
                cursor.execute("""
                    UPDATE transactions 
                    SET category_id = %s 
                    WHERE merchant_name ILIKE '%%' || %s || '%%' 
                    AND (category_id != %s OR category_id IS NULL)
                """, (req.category_id, req.rule_keyword, req.category_id))
        
        conn.commit()
        return {"status": "success", "message": "Categorization applied"}
    except Exception as e:
        conn.rollback()
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        
# --- 4. GET CATEGORIES (For Dropdowns) ---
@router.get("/categories")
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM categories ORDER BY name")
        return cursor.fetchall()
    finally:
        conn.close()