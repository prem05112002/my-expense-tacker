from fastapi import APIRouter, Depends
from ..auth import get_current_user_id
from ..database import provision_user_schema

router = APIRouter(prefix="/provision", tags=["Provision"])


@router.post("")
async def provision(user_id: str = Depends(get_current_user_id)):
    """
    Creates the Postgres schema + tables for a new user.
    Idempotent — safe to call on every login.
    """
    await provision_user_schema(user_id)
    return {"status": "ready", "user_id": user_id}
