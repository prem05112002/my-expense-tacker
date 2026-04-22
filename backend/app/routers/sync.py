from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user_id
from ..database import get_db_for_user
from ..services.sync import get_sync_status, run_email_sync

router = APIRouter(prefix="/sync", tags=["Sync"])


async def get_db(user_id: str = Depends(get_current_user_id)):
    async for session in get_db_for_user(user_id):
        yield session


@router.get("/status")
async def sync_status(user_id: str = Depends(get_current_user_id)):
    """Get current email sync status for the authenticated user."""
    return get_sync_status(user_id)


@router.post("/trigger")
async def trigger_sync(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger an email sync for the authenticated user.
    Retrieves IMAP credentials from the user's schema and runs the pipeline.
    """
    result = await run_email_sync(user_id, db)
    return {"message": "Sync completed", **result}
