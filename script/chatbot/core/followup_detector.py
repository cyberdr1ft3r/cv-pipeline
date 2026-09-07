"""
Follow-Up Detector
==================

Detects follow-up queries and implicit refinements to previous searches.

Recognizes:
- Refinements: "Narrow it down", "Add Python", "Filter by location"
- Clarifications: "Tell me more", "What about", "Also include"
- Context queries: "What we found", "Back to that search"
- Comparisons: "Compare with", "Is this better than"
- Expansions: "Show me more", "Any others", "What else"

This enables natural multi-turn conversations where queries build on previous ones.
"""

import re
from typing import Dict, Optional, List, Tuple
from enum import Enum


class FollowUpType(Enum):
    """Type of follow-up query"""
    REFINEMENT = "refinement"  # Narrow down, add filter
    CLARIFICATION = "clarification"  # Tell me more, explain
    EXPANSION = "expansion"  # Show more, what else
    CONTEXT_REFERENCE = "context_reference"  # Reference to previous query
    COMPARISON = "comparison"  # Compare X with Y
    MODIFICATION = "modification"  # Change previous criteria
    NEW_QUERY = "new_query"  # Completely new search


class FollowUpDetector:
    """
    Detects when a query is a follow-up to previous conversation.
    
    This enables:
    - Accumulating filters (narrow down from previous results)
    - Maintaining context (don't repeat the search)
    - Smart filtering (combine new criteria with old ones)
    """
    
    # Keywords for different follow-up types
    REFINEMENT_KEYWORDS = [
        'narrow', 'down', 'filter', 'also', 'add', 'include',
        'in addition', 'plus', 'besides', 'and', 'with'
    ]
    
    CLARIFICATION_KEYWORDS = [
        'tell', 'more', 'explain', 'detail', 'about',
        'elaborate', 'expand', 'what', 'how', 'why'
    ]
    
    EXPANSION_KEYWORDS = [
        'more', 'else', 'other', 'another', 'others',
        'anyone', 'anything', 'rest', 'remaining', 'more'
    ]
    
    CONTEXT_KEYWORDS = [
        'previous', 'before', 'earlier', 'that', 'those',
        'same', 'again', 'back to', 'like', 'such as'
    ]
    
    COMPARISON_KEYWORDS = [
        'compare', 'vs', 'versus', 'better', 'worse',
        'similar', 'different', 'like', 'against'
    ]
    
    def __init__(self):
        self.refinement_pattern = self._build_pattern(self.REFINEMENT_KEYWORDS)
        self.clarification_pattern = self._build_pattern(self.CLARIFICATION_KEYWORDS)
        self.expansion_pattern = self._build_pattern(self.EXPANSION_KEYWORDS)
        self.context_pattern = self._build_pattern(self.CONTEXT_KEYWORDS)
        self.comparison_pattern = self._build_pattern(self.COMPARISON_KEYWORDS)
    
    @staticmethod
    def _build_pattern(keywords: List[str]) -> str:
        """Build regex pattern from keywords"""
        return r'\b(' + '|'.join(keywords) + r')\b'
    
    def detect_followup(
        self,
        current_query: str,
        previous_query: Optional[str] = None,
        previous_intent: Optional[str] = None,
        previous_results_count: int = 0,
        conversation_turns: int = 0
    ) -> Tuple[FollowUpType, float]:
        """
        Detect if current query is a follow-up.
        
        Args:
            current_query: Current user query
            previous_query: Previous user query (if any)
            previous_intent: Intent detected for previous query
            previous_results_count: Number of results from previous query
            conversation_turns: Number of conversation turns so far
        
        Returns:
            (FollowUpType, confidence 0.0-1.0)
        """
        # If no previous conversation, this is a new query
        if conversation_turns == 0:
            return FollowUpType.NEW_QUERY, 1.0
        
        # Check for different follow-up types
        followup_type, confidence = self._classify_followup(
            current_query,
            previous_query
        )
        
        # Adjust confidence based on context
        if followup_type != FollowUpType.NEW_QUERY:
            if previous_results_count > 0:
                confidence += 0.2  # More likely a follow-up if previous results exist
            
            if previous_query and self._queries_related(current_query, previous_query):
                confidence += 0.15  # Related queries likely follow-ups
        
        confidence = min(confidence, 1.0)
        
        return followup_type, confidence
    
    def _classify_followup(
        self,
        current_query: str,
        previous_query: Optional[str] = None
    ) -> Tuple[FollowUpType, float]:
        """Classify type of follow-up"""
        query_lower = current_query.lower()
        
        # Check patterns in order of likelihood
        
        # Refinement: "Add Python to those", "Filter by location"
        if re.search(self.refinement_pattern, query_lower):
            return FollowUpType.REFINEMENT, 0.8
        
        # Expansion: "Show me more", "What else"
        if re.search(self.expansion_pattern, query_lower):
            # Check if it's really expansion or just clarification
            if re.search(r'\b(more|else|other|another|rest)\b', query_lower):
                return FollowUpType.EXPANSION, 0.75
        
        # Comparison: "Compare with", "vs"
        if re.search(self.comparison_pattern, query_lower):
            return FollowUpType.COMPARISON, 0.7
        
        # Context reference: "Like that", "Same as before"
        if re.search(self.context_pattern, query_lower):
            return FollowUpType.CONTEXT_REFERENCE, 0.65
        
        # Clarification: "Tell me more", "Explain"
        if re.search(self.clarification_pattern, query_lower):
            return FollowUpType.CLARIFICATION, 0.7
        
        # Check for similarity to previous query
        if previous_query and self._queries_related(current_query, previous_query):
            return FollowUpType.MODIFICATION, 0.6
        
        return FollowUpType.NEW_QUERY, 0.0
    
    def _queries_related(self, query1: str, query2: str) -> bool:
        """Check if two queries seem related (same entities or themes)"""
        # Simple check: look for common important words
        words1 = set(re.findall(r'\b[a-z]{4,}\b', query1.lower()))
        words2 = set(re.findall(r'\b[a-z]{4,}\b', query2.lower()))
        
        common_words = words1 & words2
        
        # If at least 2 common significant words, likely related
        return len(common_words) >= 2
    
    def is_refinement(self, query: str, previous_results_count: int = 0) -> bool:
        """Check if query is a refinement (filter/narrow down)"""
        if previous_results_count == 0:
            return False
        
        query_lower = query.lower()
        
        # Keywords that indicate refinement
        refinement_phrases = [
            r'(?:filter|narrow|down|also|add|include)',
            r'(?:but|only|just|specific)',
            r'(?:and|with)\s+(?:also|more)',
        ]
        
        for phrase in refinement_phrases:
            if re.search(phrase, query_lower):
                return True
        
        return False
    
    def is_expansion(self, query: str) -> bool:
        """Check if query asks for more information"""
        query_lower = query.lower()
        expansion_phrases = [
            r'(?:show|tell|give|list|who|what)\s+(?:more|else|others)',
            r'(?:any|anything)\s+else',
            r'(?:what)\s+(?:about|else)',
        ]
        
        for phrase in expansion_phrases:
            if re.search(phrase, query_lower):
                return True
        
        return False
    
    def extract_followup_intent(self, query: str) -> Dict[str, Optional[str]]:
        """
        Extract what the follow-up is trying to do.
        
        Returns:
            Dict with detected intent components
        """
        query_lower = query.lower()
        
        return {
            "is_refinement": self.is_refinement(query),
            "is_expansion": self.is_expansion(query),
            "has_comparison": bool(re.search(self.comparison_pattern, query_lower)),
            "references_context": bool(re.search(self.context_pattern, query_lower)),
        }
    
    def suggest_context_application(
        self,
        current_query: str,
        previous_query: str,
        previous_intent: str,
        previous_filters: Dict
    ) -> Dict:
        """
        Suggest how to apply previous context to current query.
        
        Returns:
            Dict with suggestions for filter/context application
        """
        suggestions = {
            "reuse_previous_filters": False,
            "preserve_candidate": False,
            "combine_criteria": False,
            "reason": ""
        }
        
        followup_type, confidence = self.detect_followup(
            current_query,
            previous_query
        )
        
        if followup_type == FollowUpType.REFINEMENT:
            suggestions["reuse_previous_filters"] = True
            suggestions["combine_criteria"] = True
            suggestions["reason"] = "Refinement detected - accumulate filters"
        
        elif followup_type == FollowUpType.EXPANSION:
            suggestions["reuse_previous_filters"] = True
            suggestions["reason"] = "Expansion detected - maintain previous filters"
        
        elif followup_type == FollowUpType.CLARIFICATION:
            suggestions["preserve_candidate"] = True
            suggestions["reason"] = "Clarification - focus on current candidate"
        
        elif followup_type == FollowUpType.CONTEXT_REFERENCE:
            suggestions["reuse_previous_filters"] = True
            suggestions["reason"] = "Context reference - recall previous search"
        
        return suggestions
