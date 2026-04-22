from .email_service import EmailService
from .parsers import extract_metadata, clean_text
from .db_ops import (
    get_existing_email_uids,
    get_active_rules,
    save_transaction,
    save_unmatched,
)

SOURCE_FOLDER = "sync-expense-tracker"
DEST_FOLDER = "expenses"


def _apply_rules(txn, rules: list[dict]) -> None:
    """Mutate txn in-place if a rule matches the merchant name."""
    if not txn.merchant_name:
        return
    for rule in rules:
        is_match = False
        if rule["type"] == "CONTAINS" and rule["pattern"].lower() in txn.merchant_name.lower():
            is_match = True
        elif rule["type"] == "EXACT" and rule["pattern"].lower() == txn.merchant_name.lower():
            is_match = True
        if is_match:
            print(f"[pipeline] Rule applied: {txn.merchant_name} -> {rule['new_name']}")
            txn.merchant_name = rule["new_name"]
            txn.category_id = rule["cat_id"]
            break


def run_pipeline(
    imap_user: str,
    imap_pass: str,
    schema_name: str,
    source_folder: str = SOURCE_FOLDER,
    dest_folder: str = DEST_FOLDER,
) -> dict:
    """
    Full sync job. Designed to run in a ThreadPoolExecutor (purely synchronous).

    Returns:
        {"emails_processed": int, "transactions_saved": int, "emails_unmatched": int}

    Raises:
        ConnectionError  if IMAP login fails
        RuntimeError     if a fatal DB error occurs
    """
    emails_processed = 0
    transactions_saved = 0
    emails_unmatched = 0

    # Load automation rules for this user's schema
    active_rules = get_active_rules(schema_name)
    print(f"[pipeline] Loaded {len(active_rules)} automation rules")

    # Connect to Gmail
    service = EmailService(imap_user, imap_pass)
    if not service.connect():
        raise ConnectionError("IMAP login failed — check credentials or app password")

    try:
        # Fetch all UIDs from the source folder
        email_ids = service.fetch_emails(source_folder)
        if not email_ids:
            print("[pipeline] No emails in source folder")
            return {
                "emails_processed": 0,
                "transactions_saved": 0,
                "emails_unmatched": 0,
            }

        print(f"[pipeline] Found {len(email_ids)} emails in {source_folder}")

        # Delta: skip already-processed UIDs (union of unmatched + transactions tables)
        existing_uids = get_existing_email_uids(schema_name)
        print(f"[pipeline] Already processed: {len(existing_uids)} UIDs")

        for e_id in email_ids:
            uid_str = e_id.decode("utf-8")

            if uid_str in existing_uids:
                continue

            subject, raw_body = service.get_email_content(e_id)
            if not raw_body:
                print(f"[pipeline] Empty body for UID {uid_str}, skipping")
                continue

            emails_processed += 1
            cleaned_body = clean_text(raw_body)
            transaction = extract_metadata(cleaned_body)

            if transaction:
                _apply_rules(transaction, active_rules)
                try:
                    saved = save_transaction(transaction, schema_name)
                    if saved:
                        service.move_email(e_id, dest_folder)
                        transactions_saved += 1
                    else:
                        print(f"[pipeline] Duplicate skipped for UID {uid_str}")
                except Exception as e:
                    print(f"[pipeline] Failed to save transaction for UID {uid_str}: {e}")
            else:
                save_unmatched(uid_str, subject or "", cleaned_body, schema_name)
                emails_unmatched += 1
                print(f"[pipeline] Unmatched email staged: {(subject or '')[:50]}")

    finally:
        service.close()
        print("[pipeline] IMAP connection closed")

    print(
        f"[pipeline] Done — {emails_processed} processed, "
        f"{transactions_saved} saved, {emails_unmatched} unmatched"
    )
    return {
        "emails_processed": emails_processed,
        "transactions_saved": transactions_saved,
        "emails_unmatched": emails_unmatched,
    }
