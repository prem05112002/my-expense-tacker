"""
Gmail / IMAP setup helpers:
  - Test IMAP connection
  - Create required labels
  - Search for and move existing bank emails into the sync label
"""
import imaplib
import re

IMAP_SERVER = "imap.gmail.com"
SOURCE_LABEL = "sync-expense-tracker"
PROCESSED_LABEL = "expenses"
NON_TXN_LABEL = "non-transaction"

# Patterns used to identify HDFC bank emails in the inbox
HDFC_SENDERS = [
    "alerts@hdfcbank.net",
    "noreply@hdfcbank.com",
    "hdfcbank@alerts.hdfcbank.com",
]


def test_connection(email: str, password: str) -> dict:
    """Test IMAP credentials. Returns ok + friendly message."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email, password)
        mail.logout()
        return {"ok": True, "message": "Gmail connected successfully."}
    except imaplib.IMAP4.error as e:
        msg = str(e).lower()
        if "invalid credentials" in msg or "authentication failed" in msg:
            return {
                "ok": False,
                "message": (
                    "Invalid credentials. Make sure you are using an App Password "
                    "(not your regular Gmail password) and that IMAP is enabled."
                ),
            }
        return {"ok": False, "message": f"IMAP error: {e}"}
    except Exception as e:
        return {"ok": False, "message": f"Connection error: {e}"}


def create_labels(email: str, password: str) -> dict:
    """
    Create the three Gmail labels needed by the app.
    Returns status per label (created / already_exists / error).
    """
    labels = [SOURCE_LABEL, PROCESSED_LABEL, NON_TXN_LABEL]
    results = {}
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email, password)

        for label in labels:
            # Check if label already exists by trying to select it
            status, _ = mail.select(f'"{label}"')
            if status == "OK":
                results[label] = "already_exists"
                mail.close()
            else:
                # Create the label
                create_status, resp = mail.create(f'"{label}"')
                if create_status == "OK":
                    results[label] = "created"
                else:
                    results[label] = f"error: {resp}"

        mail.logout()
        return {"ok": True, "labels": results}
    except Exception as e:
        return {"ok": False, "message": str(e), "labels": results}


def find_bank_emails(email: str, password: str) -> dict:
    """
    Search the inbox for HDFC bank emails.
    Returns count of matching emails found.
    """
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email, password)
        mail.select("INBOX")

        uids = _search_hdfc_emails(mail)
        mail.logout()
        return {"ok": True, "count": len(uids)}
    except Exception as e:
        return {"ok": False, "message": str(e), "count": 0}


def move_existing_emails(email: str, password: str) -> dict:
    """
    Find HDFC bank emails in INBOX and move them to sync-expense-tracker.
    Returns how many were moved.
    """
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email, password)
        mail.select("INBOX")

        uids = _search_hdfc_emails(mail)
        moved = 0

        for uid in uids:
            try:
                res = mail.uid("copy", uid, SOURCE_LABEL)
                if res[0] == "OK":
                    mail.uid("store", uid, "+FLAGS", "\\Deleted")
                    moved += 1
            except Exception:
                pass

        mail.expunge()
        mail.logout()
        return {"ok": True, "moved": moved}
    except Exception as e:
        return {"ok": False, "message": str(e), "moved": 0}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _search_hdfc_emails(mail: imaplib.IMAP4_SSL) -> list:
    """Return a list of UIDs for HDFC bank emails in the currently selected folder."""
    all_uids: set = set()
    for sender in HDFC_SENDERS:
        try:
            status, data = mail.uid("search", None, "FROM", sender)
            if status == "OK" and data and data[0]:
                uids = data[0].split()
                all_uids.update(uids)
        except Exception:
            pass
    return list(all_uids)
