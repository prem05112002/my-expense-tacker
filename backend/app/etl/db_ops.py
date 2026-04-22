import os
import psycopg2
from typing import Optional

_DB_HOST = os.getenv("PG_HOST")
_DB_NAME = os.getenv("DB_NAME")
_DB_USER = os.getenv("DB_USER")
_DB_PASS = os.getenv("DB_PASS")


def get_db_connection(schema_name: str) -> psycopg2.extensions.connection:
    """Connect and immediately set search_path to the user's schema."""
    conn = psycopg2.connect(
        host=_DB_HOST,
        database=_DB_NAME,
        user=_DB_USER,
        password=_DB_PASS,
        sslmode="require",
    )
    cur = conn.cursor()
    cur.execute(f"SET search_path = {schema_name}")
    cur.close()
    return conn


def get_existing_email_uids(schema_name: str) -> set[str]:
    """
    Return all UIDs already processed — union of:
    - unmatched_emails.email_uid  (failed-parse staging)
    - transactions where upi_transaction_id IS NOT NULL

    This ensures already-parsed emails are never re-inserted even if they
    were moved out of the source folder (Gap 6 fix).
    """
    conn = get_db_connection(schema_name)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT email_uid FROM unmatched_emails
            UNION
            SELECT upi_transaction_id FROM transactions
            WHERE upi_transaction_id IS NOT NULL
        """)
        return {row[0] for row in cur.fetchall()}
    except Exception as e:
        print(f"[db_ops] Failed to fetch existing UIDs: {e}")
        return set()
    finally:
        conn.close()


def get_active_rules(schema_name: str) -> list[dict]:
    """Fetch all transaction_rules for auto-categorization."""
    conn = get_db_connection(schema_name)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT pattern, new_merchant_name, category_id, match_type FROM transaction_rules"
        )
        return [
            {"pattern": r[0], "new_name": r[1], "cat_id": r[2], "type": r[3]}
            for r in cur.fetchall()
        ]
    except Exception as e:
        print(f"[db_ops] Failed to fetch rules: {e}")
        return []
    finally:
        conn.close()


def _truncate(text: Optional[str], max_length: int) -> Optional[str]:
    if text and len(text) > max_length:
        return text[:max_length]
    return text


def _check_soft_duplicate(cur, txn) -> Optional[int]:
    """Returns the ID of an existing matching transaction, or None."""
    cur.execute(
        """
        SELECT id FROM transactions
        WHERE amount = %s
          AND txn_date = %s
          AND merchant_name = %s
          AND payment_mode = %s
        LIMIT 1
        """,
        (txn.amount, txn.date, _truncate(txn.merchant_name, 255), txn.payment_mode),
    )
    row = cur.fetchone()
    return row[0] if row else None


def save_transaction(txn, schema_name: str) -> bool:
    """
    Insert to transactions table in the user's schema.
    UPI:     hard unique on upi_transaction_id — silently skips duplicates.
    Non-UPI: soft duplicate check (amount + date + merchant + payment_mode).
    Returns True if a new row was inserted, False if duplicate skipped.
    """
    conn = get_db_connection(schema_name)
    try:
        cur = conn.cursor()

        t_bank = _truncate(txn.bank_name, 50)
        t_mode = _truncate(txn.payment_mode, 20)
        t_merch = _truncate(txn.merchant_name, 255)
        t_ref = _truncate(txn.upi_transaction_id, 100)

        # Resolve category: use txn.category_id if set, else look up "Uncategorized"
        if txn.category_id:
            final_cat_id = txn.category_id
        else:
            cur.execute("SELECT id FROM categories WHERE name = 'Uncategorized'")
            row = cur.fetchone()
            final_cat_id = row[0] if row else None

        if t_ref:
            # UPI — hard unique constraint
            cur.execute(
                """
                INSERT INTO transactions
                    (bank_name, amount, payment_type, payment_mode,
                     txn_date, merchant_name, upi_transaction_id, category_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (upi_transaction_id) DO NOTHING
                """,
                (t_bank, txn.amount, txn.payment_type,
                 t_mode, txn.date, t_merch, t_ref, final_cat_id),
            )
            inserted = cur.rowcount > 0
        else:
            # Non-UPI — soft duplicate check (skip if already exists)
            original_id = _check_soft_duplicate(cur, txn)
            if original_id:
                print(f"[db_ops] Soft duplicate skipped: matches transaction #{original_id}")
                return False

            cur.execute(
                """
                INSERT INTO transactions
                    (bank_name, amount, payment_type, payment_mode,
                     txn_date, merchant_name, upi_transaction_id, category_id)
                VALUES (%s, %s, %s, %s, %s, %s, NULL, %s)
                """,
                (t_bank, txn.amount, txn.payment_type,
                 t_mode, txn.date, t_merch, final_cat_id),
            )
            inserted = True

        conn.commit()
        return inserted
    except Exception as e:
        print(f"[db_ops] DB insert error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def save_unmatched(email_uid: str, subject: str, body: str, schema_name: str):
    """Insert to unmatched_emails staging table. ON CONFLICT DO NOTHING."""
    conn = get_db_connection(schema_name)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO unmatched_emails (email_uid, email_subject, email_body, received_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (email_uid) DO NOTHING
            """,
            (str(email_uid), subject, body),
        )
        conn.commit()
    except Exception as e:
        print(f"[db_ops] Error saving unmatched email: {e}")
        conn.rollback()
    finally:
        conn.close()
