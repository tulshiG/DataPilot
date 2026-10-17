"""
Conversational Analytics — Session Manager
=============================================
Manages conversation sessions so users can ask follow-up questions
that reference previous queries.

Example conversation:
    Turn 1: "Show me total revenue by city"
    Turn 2: "Now filter that by Mumbai"        → understands "that" = previous query
    Turn 3: "Sort it descending"               → modifies the last result
    Turn 4: "What about by region instead?"    → changes group_by, keeps metric

Sessions are stored in-memory with auto-expiry (configurable TTL).
No database persistence needed — conversations are ephemeral.
"""

import logging
import time
import uuid
from typing import Optional
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Default session TTL: 30 minutes of inactivity
DEFAULT_SESSION_TTL = 1800

# Max sessions per workspace
MAX_SESSIONS = 200

# Session store: workspace_id → {session_id → ConversationSession}
_sessions: dict[int, TTLCache] = {}


class ConversationTurn:
    """A single turn in a conversation."""

    def __init__(self, query: str, spec: dict | None = None,
                 result_summary: str | None = None, sql: str | None = None):
        self.query = query
        self.spec = spec or {}
        self.result_summary = result_summary
        self.sql = sql
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "spec": self.spec,
            "result_summary": self.result_summary,
            "sql": self.sql,
            "timestamp": self.timestamp,
        }


class ConversationSession:
    """A multi-turn conversation session."""

    def __init__(self, workspace_id: int, user_id: int):
        self.session_id = str(uuid.uuid4())
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.turns: list[ConversationTurn] = []
        self.created_at = time.time()
        self.last_active = time.time()

    def add_turn(self, turn: ConversationTurn):
        self.turns.append(turn)
        self.last_active = time.time()

    @property
    def last_turn(self) -> ConversationTurn | None:
        return self.turns[-1] if self.turns else None

    @property
    def last_spec(self) -> dict:
        return self.last_turn.spec if self.last_turn else {}

    @property
    def last_query(self) -> str:
        return self.last_turn.query if self.last_turn else ""

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def get_history_for_llm(self, max_turns: int = 3) -> list[dict]:
        """Get recent history formatted for LLM context."""
        recent = self.turns[-max_turns:]
        return [
            {
                "query": t.query,
                "response_summary": t.result_summary or "",
            }
            for t in recent
        ]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "turn_count": self.turn_count,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "turns": [t.to_dict() for t in self.turns],
        }


def get_or_create_session(
    workspace_id: int,
    user_id: int,
    session_id: str | None = None,
) -> ConversationSession:
    """
    Get an existing session or create a new one.

    Parameters
    ----------
    workspace_id : int
    user_id : int
    session_id : str, optional
        If provided, try to resume this session. If expired or not found,
        create a new one.
    """
    if workspace_id not in _sessions:
        _sessions[workspace_id] = TTLCache(maxsize=MAX_SESSIONS, ttl=DEFAULT_SESSION_TTL)

    cache = _sessions[workspace_id]

    # Try to resume existing session
    if session_id and session_id in cache:
        session = cache[session_id]
        session.last_active = time.time()
        return session

    # Create new session
    session = ConversationSession(workspace_id, user_id)
    cache[session.session_id] = session
    logger.debug(f"New conversation session: {session.session_id} (workspace={workspace_id})")
    return session


def record_turn(
    session: ConversationSession,
    query: str,
    spec: dict | None = None,
    result_summary: str | None = None,
    sql: str | None = None,
):
    """Record a completed query turn in the session."""
    turn = ConversationTurn(query, spec, result_summary, sql)
    session.add_turn(turn)
    logger.debug(f"Session {session.session_id}: turn {session.turn_count} recorded")


def get_session(workspace_id: int, session_id: str) -> Optional[ConversationSession]:
    """Get a session by ID. Returns None if expired or not found."""
    cache = _sessions.get(workspace_id)
    if cache and session_id in cache:
        return cache[session_id]
    return None


def list_sessions(workspace_id: int) -> list[dict]:
    """List all active sessions for a workspace."""
    cache = _sessions.get(workspace_id)
    if not cache:
        return []
    return [
        {
            "session_id": s.session_id,
            "user_id": s.user_id,
            "turn_count": s.turn_count,
            "last_active": s.last_active,
        }
        for s in cache.values()
    ]
