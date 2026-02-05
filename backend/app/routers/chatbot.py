from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, Optional
from ..database import get_db
from ..services.agents import process_chat_message, get_rate_limit_status
from ..schemas.chatbot import ChatRequest, ChatResponse

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post("/ask", response_model=ChatResponse)
async def ask_chatbot(
    chat: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the financial assistant chatbot.

    The chatbot uses LLM-powered natural language understanding to handle
    complex queries including hypothetical scenarios and multi-turn conversations.

    **Session Support:**
    - Include `session_id` to continue a conversation
    - The response includes the `session_id` to use for follow-up messages
    - Sessions expire after 30 minutes of inactivity

    **Example queries:**
    - Simple: "What's my remaining budget?"
    - Category: "How much do I spend on food?"
    - Trends: "What are my spending trends?"
    - Affordability: "Can I buy an iPhone 15 in EMI?"
    - Complex: "If I reduce food spending by 10k per month, can I afford Japan flights in 6 months?"
    - Time range: "How much have I spent on fuel in the past 3 months?"
    - Goal planning: "Can I save ₹50,000 in 6 months?"
    - Budget forecast: "Will I stay under budget this month?"
    - Follow-up: "What about last month?" (continues previous query context)

    **Response intents:**
    - "conversational": Natural language response from LLM analysis
    - "clarify": Chatbot needs more information
    - Legacy intents (fallback): budget_status, category_spend, trends, etc.

    **Privacy:** Financial data is computed locally. Only aggregated summaries
    and product names are sent to the LLM for analysis and formatting.
    """
    result = await process_chat_message(
        db,
        chat.message,
        session_id=chat.session_id
    )
    return ChatResponse(**result)


@router.get("/rate-limit")
async def get_rate_limit():
    """
    Get current rate limit status for LLM API calls.

    Returns daily and per-minute remaining requests.
    """
    return get_rate_limit_status()
