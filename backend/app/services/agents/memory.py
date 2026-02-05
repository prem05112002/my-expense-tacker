"""Session management for multi-turn conversations.

Extracted from chatbot.py for use in the agent system.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from ...schemas.chatbot import ChatQueryParams


class ConversationSession:
    """Stores conversation state for multi-turn interactions."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[Dict[str, Any]] = []  # Last N messages
        self.last_query_params: Optional[ChatQueryParams] = None
        self.last_results: Optional[Dict[str, Any]] = None
        self.last_accessed: float = time.time()

    def add_message(
        self,
        role: str,
        content: str,
        params: Optional[ChatQueryParams] = None
    ) -> None:
        """Add a message to the conversation history.

        Args:
            role: "user" or "assistant"
            content: Message content
            params: Optional parsed parameters for assistant messages
        """
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "params": params.model_dump() if params else None,
        })
        # Keep only last 10 messages
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]
        self.last_accessed = time.time()

    def get_history_for_llm(self) -> str:
        """Format conversation history for LLM context.

        Returns:
            Formatted string of recent conversation history
        """
        if not self.messages:
            return "No previous conversation."

        history_lines = []
        for msg in self.messages[-6:]:  # Last 6 messages for context
            role = "User" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")

        return "\n".join(history_lines)

    def get_last_category(self) -> Optional[str]:
        """Get the last category mentioned in the conversation.

        Useful for follow-up queries like "what about last month?"
        """
        for msg in reversed(self.messages):
            params = msg.get("params")
            if params and params.get("category_name"):
                return params["category_name"]
        return None

    def get_last_time_range(self) -> Optional[Dict[str, Any]]:
        """Get the last time range mentioned in the conversation."""
        for msg in reversed(self.messages):
            params = msg.get("params")
            if params and params.get("time_range"):
                return params["time_range"]
        return None


class SessionManager:
    """Manages conversation sessions with TTL and cleanup."""

    TTL_SECONDS = 30 * 60  # 30 minutes
    MAX_SESSIONS = 1000

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(
        self,
        session_id: Optional[str] = None
    ) -> ConversationSession:
        """Get existing session or create a new one.

        Args:
            session_id: Optional existing session ID

        Returns:
            ConversationSession instance
        """
        self._maybe_cleanup()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_accessed = time.time()
            return session

        # Create new session
        new_id = session_id or str(uuid.uuid4())
        session = ConversationSession(new_id)
        self._sessions[new_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get a session by ID without creating.

        Args:
            session_id: Session ID

        Returns:
            ConversationSession or None if not found
        """
        session = self._sessions.get(session_id)
        if session:
            session.last_accessed = time.time()
        return session

    def _maybe_cleanup(self) -> None:
        """Remove expired sessions."""
        now = time.time()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_accessed > self.TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]

        # If still over limit, remove oldest
        if len(self._sessions) > self.MAX_SESSIONS:
            sorted_sessions = sorted(
                self._sessions.items(),
                key=lambda x: x[1].last_accessed
            )
            for sid, _ in sorted_sessions[:len(self._sessions) - self.MAX_SESSIONS]:
                del self._sessions[sid]

    def session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)


# Global session manager instance
_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Get the global session manager."""
    return _session_manager
