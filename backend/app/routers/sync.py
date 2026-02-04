from fastapi import APIRouter, BackgroundTasks
from ..services.sync import get_sync_status, run_email_sync

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.get("/status")
async def sync_status():
    """Get current email sync status."""
    return get_sync_status()


@router.post("/trigger")
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Trigger email sync from the ETL pipeline.
    Returns immediately with status, sync runs in background.
    """
    # Check if already running
    status = get_sync_status()
    if status["status"] == "running":
        return {"message": "Sync already in progress", **status}

    # Run sync
    result = await run_email_sync()
    return {"message": "Sync completed", **result}
