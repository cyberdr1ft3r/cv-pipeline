"""
Conversation Context Manager
=============================

Maintains conversation state and context across multiple turns.
Tracks what the user is searching for, current candidate, filters, and conversation theme.

This enables:
- Multi-turn awareness (remembers previous queries)
- Implicit reference tracking (knows current focus)
- Filter accumulation (stacks search criteria)
- Conversation flow tracking (understands user goal)
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class ConversationTheme(Enum):
    """Type of conversation in progress"""
    UNKNOWN = "unknown"
    HIRING_SEARCH = "hiring_search"  # Looking for candidates to hire
    PORTFOLIO_REVIEW = "portfolio_review"  # Reviewing specific people
    SKILL_DISCOVERY = "skill_discovery"  # Understanding what skills exist
    COMPARISON = "comparison"  # Comparing candidates
    DETAILED_PROFILE = "detailed_profile"  # Deep dive into one person


class ConversationState(Enum):
    """Conversation flow state"""
    GREETING = "greeting"  # User just greeted
    TOPIC_INQUIRY = "topic_inquiry"  # User asking about available topics
    INFORMATION_SEEKING = "information_seeking"  # User learning about topic
    SPECIFIC_SEARCH = "specific_search"  # User making specific query
    RESULTS_REVIEW = "results_review"  # Discussing search results
    FOLLOW_UP = "follow_up"  # Following up on previous results
    CLARIFICATION = "clarification"  # User clarifying/refining query


@dataclass
class SearchFilter:
    """Active search criteria"""
    skills: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    seniority_level: Optional[str] = None  # junior, mid, senior
    custom_criteria: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def is_empty(self) -> bool:
        """Check if any filters are active"""
        return (
            not self.skills and
            not self.locations and
            self.experience_min is None and
            self.experience_max is None and
            not self.seniority_level and
            not self.custom_criteria
        )
    
    def add_skill(self, skill: str) -> None:
        """Add skill to filter"""
        if skill and skill not in self.skills:
            self.skills.append(skill)
    
    def add_location(self, location: str) -> None:
        """Add location to filter"""
        if location and location not in self.locations:
            self.locations.append(location)


@dataclass
class ConversationTurn:
    """Single conversation turn"""
    turn_number: int
    user_query: str
    detected_intent: str
    extracted_entities: Dict[str, Any]
    bot_response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ConversationContext:
    """
    Maintains full conversation state across turns.
    
    Tracks:
    - Current candidate (if user focused on one person)
    - Active search filters (accumulated criteria)
    - Conversation theme (what user is trying to do)
    - Turn history (for reference resolution)
    - Implicit references (pronouns, "them", etc.)
    """
    
    def __init__(self, session_id: str, max_history: int = 15):
        self.session_id = session_id
        self.max_history = max_history
        
        # Conversation state
        self.current_candidate: Optional[Dict[str, Any]] = None
        self.active_filters = SearchFilter()
        self.conversation_theme = ConversationTheme.UNKNOWN
        self.conversation_state = ConversationState.GREETING  # Track flow state
        self.turn_history: List[ConversationTurn] = []
        self.last_search_results: List[Dict] = []  # For follow-ups about results
        self.last_topic_discussed: Optional[str] = None  # Track current topic
        
        # Previous query results (for follow-up context)
        self.last_search_results: List[Dict[str, Any]] = []
        self.last_search_query: Optional[str] = None
        self.last_search_intent: Optional[str] = None
        
        # Implicit references
        self.last_mentioned_candidate: Optional[Dict[str, Any]] = None
        self.last_mentioned_skill: Optional[str] = None
        self.last_mentioned_location: Optional[str] = None
    
    def add_turn(
        self,
        user_query: str,
        detected_intent: str,
        extracted_entities: Dict[str, Any],
        bot_response: str
    ) -> None:
        """Record a conversation turn"""
        turn = ConversationTurn(
            turn_number=len(self.turn_history) + 1,
            user_query=user_query,
            detected_intent=detected_intent,
            extracted_entities=extracted_entities,
            bot_response=bot_response
        )
        self.turn_history.append(turn)
        
        # Keep only recent history
        if len(self.turn_history) > self.max_history:
            self.turn_history = self.turn_history[-self.max_history:]
    
    def set_current_candidate(self, candidate: Dict[str, Any]) -> None:
        """Set the candidate currently being discussed"""
        self.current_candidate = candidate
        self.last_mentioned_candidate = candidate
        
        # Switch theme if needed
        if self.conversation_theme != ConversationTheme.DETAILED_PROFILE:
            self.conversation_theme = ConversationTheme.DETAILED_PROFILE
    
    def clear_current_candidate(self) -> None:
        """Clear the current candidate"""
        self.current_candidate = None
    
    def add_search_filter(
        self,
        skills: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        experience_min: Optional[int] = None,
        experience_max: Optional[int] = None,
        seniority_level: Optional[str] = None
    ) -> None:
        """Add/update search filters (accumulates criteria)"""
        if skills:
            for skill in skills:
                self.active_filters.add_skill(skill)
                self.last_mentioned_skill = skill
        
        if locations:
            for loc in locations:
                self.active_filters.add_location(loc)
                self.last_mentioned_location = loc
        
        if experience_min is not None:
            self.active_filters.experience_min = experience_min
        
        if experience_max is not None:
            self.active_filters.experience_max = experience_max
        
        if seniority_level:
            self.active_filters.seniority_level = seniority_level
    
    def clear_search_filters(self) -> None:
        """Clear all accumulated filters"""
        self.active_filters = SearchFilter()
    
    def get_active_filters(self) -> Dict[str, Any]:
        """Get current active filters as dictionary"""
        filters = self.active_filters.to_dict()
        # Remove empty values
        return {k: v for k, v in filters.items() if v}
    
    def set_search_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        intent: str
    ) -> None:
        """Store last search results for context"""
        self.last_search_results = results
        self.last_search_query = query
        self.last_search_intent = intent
    
    def get_search_context(self) -> Dict[str, Any]:
        """Get context from last search"""
        return {
            "query": self.last_search_query,
            "intent": self.last_search_intent,
            "result_count": len(self.last_search_results),
            "results": self.last_search_results
        }
    
    def infer_theme(self, intent: str) -> ConversationTheme:
        """Infer conversation theme from intent"""
        theme_map = {
            "search": ConversationTheme.HIRING_SEARCH,
            "ranking": ConversationTheme.HIRING_SEARCH,
            "filter": ConversationTheme.HIRING_SEARCH,
            "profile": ConversationTheme.PORTFOLIO_REVIEW,
            "comparison": ConversationTheme.COMPARISON,
            "gap_analysis": ConversationTheme.PORTFOLIO_REVIEW,
            "recommendation": ConversationTheme.HIRING_SEARCH,
            "aggregation": ConversationTheme.SKILL_DISCOVERY,
        }
        self.conversation_theme = theme_map.get(
            intent,
            ConversationTheme.UNKNOWN
        )
        return self.conversation_theme
    
    def get_turn_history_text(self, last_n: int = 5) -> str:
        """Get recent turn history as readable text"""
        recent_turns = self.turn_history[-last_n:]
        text = ""
        for turn in recent_turns:
            text += f"Turn {turn.turn_number}:\n"
            text += f"  User: {turn.user_query}\n"
            text += f"  Bot: {turn.bot_response[:100]}...\n\n"
        return text
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dictionary"""
        return {
            "session_id": self.session_id,
            "current_candidate": self.current_candidate,
            "active_filters": self.active_filters.to_dict(),
            "conversation_theme": self.conversation_theme.value,
            "turn_count": len(self.turn_history),
            "last_search_query": self.last_search_query,
            "last_search_intent": self.last_search_intent,
        }
    
    def __repr__(self) -> str:
        """String representation"""
        candidate_name = (
            self.current_candidate.get("candidate_name", "Unknown")
            if self.current_candidate else "None"
        )
        filters_count = sum([
            len(self.active_filters.skills),
            len(self.active_filters.locations),
            1 if self.active_filters.experience_min else 0,
            1 if self.active_filters.seniority_level else 0,
        ])
        return (
            f"ConversationContext("
            f"turns={len(self.turn_history)}, "
            f"theme={self.conversation_theme.value}, "
            f"current_candidate={candidate_name}, "
            f"active_filters={filters_count}"
            f")"
        )
