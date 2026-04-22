import asyncio
from datetime import datetime
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..crypto import decrypt
from ..database import _safe_schema_name
from ..etl.pipeline import run_pipeline


class SyncStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Per-user sync state keyed by user_id (resets on server restart)
_sync_states: dict[str, dict] = {}


def _default_state() -> dict:
    return {
        "status": SyncStatus.IDLE,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "emails_processed": 0,
        "transactions_saved": 0,
        "emails_unmatched": 0,
    }


def get_sync_status(user_id: str) -> dict:
    state = _sync_states.get(user_id, _default_state())
    return {
        "status": state["status"],
        "started_at": state["started_at"].isoformat() if state["started_at"] else None,
        "completed_at": state["completed_at"].isoformat() if state["completed_at"] else None,
        "error": state["error"],
        "emails_processed": state["emails_processed"],
        "transactions_saved": state["transactions_saved"],
        "emails_unmatched": state["emails_unmatched"],
    }


async def run_email_sync(user_id: str, db: AsyncSession) -> dict:
    """
    Trigger an email sync for a specific user.
    Retrieves their IMAP credentials from user_settings, then runs the
    pipeline in a thread pool to avoid blocking the async event loop.
    """
    state = _sync_states.get(user_id, _default_state())

    if state["status"] == SyncStatus.RUNNING:
        return {"error": "sync_in_progress", **get_sync_status(user_id)}

    schema = _safe_schema_name(user_id)

    # Retrieve IMAP credentials from the user's schema
    # (db session already has search_path set to this schema via get_db_for_user)
    result = await db.execute(
        text("SELECT imap_user, imap_pass_enc, imap_configured FROM user_settings LIMIT 1")
    )
    row = result.fetchone()

    if not row or not row.imap_configured:
        return {
            "error": "imap_not_configured",
            "message": "Complete Gmail setup before syncing",
        }

    imap_user = row.imap_user
    try:
        imap_pass = decrypt(row.imap_pass_enc)
    except Exception:
        return {
            "error": "imap_decrypt_failed",
            "message": "Could not decrypt stored credentials. Re-enter your app password.",
        }

    # Mark as running
    _sync_states[user_id] = {
        **_default_state(),
        "status": SyncStatus.RUNNING,
        "started_at": datetime.now(),
    }

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            run_pipeline,
            imap_user,
            imap_pass,
            schema,
        )
        _sync_states[user_id].update({
            "status": SyncStatus.COMPLETED,
            "completed_at": datetime.now(),
            "emails_processed": result["emails_processed"],
            "transactions_saved": result["transactions_saved"],
            "emails_unmatched": result["emails_unmatched"],
        })
        print(
            f"[sync] User {user_id}: completed — "
            f"{result['emails_processed']} processed, "
            f"{result['transactions_saved']} saved"
        )
    except ConnectionError as e:
        _sync_states[user_id].update({
            "status": SyncStatus.FAILED,
            "completed_at": datetime.now(),
            "error": "imap_auth_failed",
        })
        print(f"[sync] User {user_id}: IMAP auth failed — {e}")
    except Exception as e:
        error_msg = str(e)
        _sync_states[user_id].update({
            "status": SyncStatus.FAILED,
            "completed_at": datetime.now(),
            "error": error_msg,
        })
        print(f"[sync] User {user_id}: sync failed — {error_msg}")
        import traceback
        traceback.print_exc()

    return get_sync_status(user_id)
