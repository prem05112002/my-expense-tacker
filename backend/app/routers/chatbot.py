from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict
from ..database import get_db
from ..services import chatbot as chatbot_service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: str
    requires_llm: bool
    rate_limit: Dict[str, Any]


@router.post("/ask", response_model=ChatResponse)
async def ask_chatbot(
    chat: ChatMessage,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the financial assistant chatbot.

    Supported queries:
    - Budget status: "What's my remaining budget?"
    - Category spending: "How much do I spend on food?"
    - Trends: "What are my spending trends?"
    - Affordability: "Can I buy an iPhone 15 in EMI?"
    - Savings: "Where can I cut expenses?"

    Privacy: Financial data is computed locally. Only product names
    are sent to the LLM for price lookups.
    """
    result = await chatbot_service.process_chat_message(db, chat.message)
    return ChatResponse(**result)


@router.get("/rate-limit")
async def get_rate_limit():
    """
    Get current rate limit status for LLM API calls.

    Returns daily and per-minute remaining requests.
    """
    return chatbot_service.get_rate_limit_status()
