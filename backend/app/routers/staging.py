from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from .. import schemas, services
from ..database import get_db_for_user
from ..auth import get_current_user_id


async def get_db(user_id: str = Depends(get_current_user_id)):
    async for session in get_db_for_user(user_id):
        yield session

router = APIRouter(prefix="/staging", tags=["staging"])

@router.get("", response_model=List[schemas.StagingTransactionOut])
async def get_items(db: AsyncSession = Depends(get_db)):
    return await services.get_staging_transactions(db)

@router.delete("/{staging_id}")
async def dismiss(
    staging_id: int, 
    background_tasks: BackgroundTasks, # 👈 Inject BackgroundTasks
    db: AsyncSession = Depends(get_db)
):
    # Pass background_tasks to service
    return await services.dismiss_staging_item(db, staging_id, background_tasks)

@router.post("/convert")
async def convert(
    data: schemas.StagingConvert, 
    background_tasks: BackgroundTasks, # 👈 Inject BackgroundTasks
    db: AsyncSession = Depends(get_db)
):
    # Pass background_tasks to service
    return await services.convert_staging_to_transaction(db, data, background_tasks)