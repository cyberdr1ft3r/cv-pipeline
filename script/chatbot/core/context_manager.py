"""
Context Manager Module
Manages conversation context across turns
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ContextManager:
    """Manage conversation context across turns"""
    
    def __init__(self, cache):
        """
        Initialize context manager
        
        Args:
            cache: Cache instance for storing context
        """
        self.cache = cache
    
    def get_context(self, session_id: str) -> Dict:
        """
        Get current context for session
        
        Returns:
            {
                "session_id": "12345",
                "created_at": "2026-01-29T10:30:00",
                "history": [],
                "last_candidate": None,
                "last_intent": None,
                "recent_candidates": [],
                "active_filters": {},
                "focus_topic": None
            }
        """
        
        cache_key = f"context_{session_id}"
        cached = self.cache.get(cache_key)
        
        if cached:
            logger.debug(f"Retrieved context from cache for session {session_id}")
            if isinstance(cached, str):
                return json.loads(cached)
            return cached
        
        # Initialize new context
        logger.debug(f"Initializing new context for session {session_id}")
        return self._init_context(session_id)
    
    def _init_context(self, session_id: str) -> Dict:
        """Initialize new conversation context"""
        
        return {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "history": [],
            "last_candidate": None,
            "last_intent": None,
            "recent_candidates": [],
            "active_filters": {},
            "focus_topic": None,
            "turn_count": 0
        }
    
    def add_turn(
        self,
        session_id: str,
        user_query: str,
        bot_response: str,
        intent: str,
        entities: Dict
    ) -> Dict:
        """
        Add conversation turn to context
        
        Args:
            session_id: Session ID
            user_query: User's question
            bot_response: Bot's response
            intent: Detected intent
            entities: Extracted entities
        
        Returns:
            Updated context
        """
        
        context = self.get_context(session_id)
        
        # Add new turn
        turn = {
            "timestamp": datetime.now().isoformat(),
            "user": user_query,
            "bot": bot_response,
            "intent": intent,
            "entities": entities
        }
        
        context["history"].append(turn)
        context["turn_count"] = len(context["history"])
        
        # Limit history to last 15 turns (to save memory)
        if len(context["history"]) > 15:
            context["history"] = context["history"][-15:]
        
        # Update context state
        if entities.get("candidates"):
            context["last_candidate"] = entities["candidates"][0]
            # Add to recent candidates
            if context["last_candidate"] not in context.get("recent_candidates", []):
                context["recent_candidates"].append(context["last_candidate"])
            # Limit recent to last 5
            context["recent_candidates"] = context["recent_candidates"][-5:]
        
        context["last_intent"] = intent
        
        if entities.get("skills"):
            context["focus_topic"] = entities["skills"][0]
        
        # Merge active filters
        if entities.get("criteria"):
            context["active_filters"].update(entities["criteria"])
        
        # Cache for 24 hours
        cache_key = f"context_{session_id}"
        self.cache.set(cache_key, json.dumps(context), ttl=86400)
        
        logger.debug(f"Added turn to context for session {session_id}. Total turns: {context['turn_count']}")
        
        return context
    
    def clear_context(self, session_id: str):
        """Clear context for session"""
        cache_key = f"context_{session_id}"
        self.cache.delete(cache_key)
        logger.info(f"Cleared context for session {session_id}")
    
    def get_conversation_summary(self, session_id: str) -> str:
        """Get a summary of conversation for LLM context"""
        
        context = self.get_context(session_id)
        
        if not context.get("history"):
            return "This is the start of the conversation."
        
        # Build summary of last 3 turns
        summary_turns = context["history"][-3:]
        
        summary = "Recent conversation:\n"
        for turn in summary_turns:
            summary += f"- User: {turn['user'][:80]}...\n"
            summary += f"- Bot: {turn['bot'][:80]}...\n"
        
        return summary
    
    def get_implicit_context(self, session_id: str) -> Dict:
        """
        Get implicit context for resolving pronouns and references
        
        Returns:
            {
                "last_candidate": "John Doe",
                "recent_candidates": ["John", "Jane"],
                "last_intent": "profile",
                "focus_topic": "Docker",
                "active_filters": {"location": "Paris"}
            }
        """
        
        context = self.get_context(session_id)
        
        return {
            "last_candidate": context.get("last_candidate"),
            "recent_candidates": context.get("recent_candidates", []),
            "last_intent": context.get("last_intent"),
            "focus_topic": context.get("focus_topic"),
            "active_filters": context.get("active_filters", {})
        }
