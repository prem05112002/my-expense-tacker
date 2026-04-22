import asyncio
import imaplib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..auth import get_current_user_id
from ..database import get_db_for_user
from ..crypto import encrypt

router = APIRouter(prefix="/gmail-setup", tags=["Gmail Setup"])

REQUIRED_LABELS = ["sync-expense-tracker", "expenses", "non-transaction"]


class GmailCredentials(BaseModel):
    email: str
    app_password: str


async def _get_user_db(user_id: str = Depends(get_current_user_id)):
    async for session in get_db_for_user(user_id):
        yield session


def _test_imap_connection(email: str, app_password: str) -> list[str]:
    """Runs blocking IMAP I/O in a thread — must not be called from the event loop directly."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        try:
            mail.login(email, app_password)
        except imaplib.IMAP4.error:
            raise ValueError("IMAP login failed — check email and app password")
        _, folders = mail.list()
        existing = [f.decode().split('"."')[-1].strip().strip('"') for f in folders]
        return [label for label in REQUIRED_LABELS if label in existing]
    finally:
        try:
            mail.logout()
        except Exception:
            pass


@router.post("/save")
async def save_and_verify(
    creds: GmailCredentials,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(_get_user_db),
):
    """
    Verifies the IMAP connection is working, then saves the credentials.
    Returns which of the 3 required labels already exist in the user's Gmail.
    """
    # 1. Test the connection in a thread so it doesn't block the event loop
    try:
        found_labels = await asyncio.to_thread(_test_imap_connection, creds.email, creds.app_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save encrypted credentials
    enc_pass = encrypt(creds.app_password)
    await db.execute(text("""
        UPDATE user_settings
        SET imap_user = :email, imap_pass_enc = :enc_pass, imap_configured = FALSE
    """), {"email": creds.email, "enc_pass": enc_pass})
    await db.commit()

    return {
        "connection": "ok",
        "labels_found": found_labels,
        "labels_missing": [l for l in REQUIRED_LABELS if l not in found_labels],
    }


@router.post("/mark-ready")
async def mark_configured(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(_get_user_db),
):
    """Called by the frontend after the user confirms all labels are in place."""
    await db.execute(text("UPDATE user_settings SET imap_configured = TRUE"))
    await db.commit()
    return {"status": "configured"}


@router.get("/status")
async def setup_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(_get_user_db),
):
    """Frontend polls this to know whether to show the setup wizard."""
    result = await db.execute(text(
        "SELECT imap_user, imap_configured FROM user_settings LIMIT 1"
    ))
    row = result.fetchone()
    return {
        "configured": bool(row and row.imap_configured),
        "email": row.imap_user if row else None,
    }
