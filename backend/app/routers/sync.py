from fastapi import APIRouter, Depends

from ..auth import get_current_user_id
from ..services.sync import get_sync_status, run_email_sync

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.get("/status")
async def sync_status(user_id: str = Depends(get_current_user_id)):
    """Get current email sync status for the authenticated user."""
    return get_sync_status(user_id)


@router.post("/trigger")
async def trigger_sync(user_id: str = Depends(get_current_user_id)):
    """
    Trigger an email sync for the authenticated user.
    Retrieves IMAP credentials from the user's schema and runs the pipeline.
    """
    result = await run_email_sync(user_id)
    return {"message": "Sync completed", **result}
