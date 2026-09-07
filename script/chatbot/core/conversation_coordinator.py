"""
Conversation Coordinator - Integrates all 4 human-conversation components
Sits between orchestrator and existing components to add context awareness
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

try:
    # Try relative imports (when used as part of package)
    from .conversation_context import ConversationContext, ConversationTheme
    from .pronoun_resolver import PronounResolver
    from .followup_detector import FollowUpDetector, FollowUpType
    from .response_variator import ResponseVariator, ResponseContext
except ImportError:
    # Fall back to absolute imports (when run as script)
    from conversation_context import ConversationContext, ConversationTheme
    from pronoun_resolver import PronounResolver
    from followup_detector import FollowUpDetector, FollowUpType
    from response_variator import ResponseVariator, ResponseContext

logger = logging.getLogger(__name__)


class ConversationCoordinator:
    """
    Coordinates all human-conversation components.
    
    This layer sits between the orchestrator and existing components:
    
    Flow:
    1. Initialize/load ConversationContext for session
    2. Apply PronounResolver to transform query with pronouns resolved
    3. Detect follow-ups with FollowUpDetector
    4. Use ResponseVariator to generate natural responses
    5. Update ConversationContext with new turn
    
    This is a non-breaking integration layer - can be added without
    modifying existing orchestrator logic.
    """
    
    def __init__(self, cache=None):
        """
        Initialize conversation coordinator.
        
        Args:
            cache: Optional cache for storing conversation contexts
        """
        self.cache = cache
        self.contexts: Dict[str, ConversationContext] = {}
        
        self.pronoun_resolver = PronounResolver()
        self.followup_detector = FollowUpDetector()
        self.response_variator = ResponseVariator()
        
        logger.info("ConversationCoordinator initialized")
    
    def get_or_create_context(self, session_id: str) -> ConversationContext:
        """Get existing context or create new one"""
        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext(session_id=session_id)
            logger.debug(f"Created new context for session: {session_id}")
        
        return self.contexts[session_id]
    
    def preprocess_query(
        self,
        query: str,
        session_id: str
    ) -> Tuple[str, Dict]:
        """
        Preprocess query: resolve pronouns and detect follow-ups.
        
        Args:
            query: Original user query
            session_id: Conversation session ID
        
        Returns:
            (resolved_query, preprocessing_info) where:
            - resolved_query: Query with pronouns resolved
            - preprocessing_info: {
                "had_pronouns": bool,
                "resolved_pronouns": {...},
                "followup_type": FollowUpType or None,
                "followup_confidence": float,
                "suggested_context": str or None
              }
        """
        context = self.get_or_create_context(session_id)
        
        info = {
            "had_pronouns": False,
            "resolved_pronouns": {},
            "followup_type": None,
            "followup_confidence": 0.0,
            "suggested_context": None
        }
        
        # Step 1: Resolve pronouns if present
        if self.pronoun_resolver.has_pronouns(query):
            info["had_pronouns"] = True
            
            resolved_query = self.pronoun_resolver.resolve_pronouns(
                query=query,
                current_candidate=context.current_candidate,
                last_search_results=context.last_search_results,
                conversation_history=[t.user_query for t in context.turn_history[-5:]]  # Last 5 turns
            )
            
            if resolved_query != query:
                info["resolved_pronouns"] = (
                    self.pronoun_resolver.extract_pronoun_references(query)
                )
                query = resolved_query
                logger.debug(f"Resolved pronouns: {info['resolved_pronouns']}")
        
        # Step 2: Detect follow-ups
        if len(context.turn_history) > 0:
            previous_query = context.turn_history[-1].user_query
            previous_intent = context.turn_history[-1].detected_intent if context.turn_history else None
            
            followup_type, confidence = self.followup_detector.detect_followup(
                current_query=query,
                previous_query=previous_query,
                previous_intent=previous_intent,
                previous_results_count=len(context.last_search_results) if context.last_search_results else 0,
                conversation_turns=len(context.turn_history)
            )
            
            if followup_type != FollowUpType.NEW_QUERY:
                info["followup_type"] = followup_type
                info["followup_confidence"] = confidence
                
                # Get suggested context application
                suggested = self.followup_detector.suggest_context_application(
                    current_query=query,
                    previous_query=previous_query,
                    previous_intent=previous_intent,
                    previous_filters=context.get_active_filters() if hasattr(context, 'get_active_filters') else {}
                )
                
                if suggested and any(suggested.values()):
                    info["suggested_context"] = suggested.get('reason', '')
                    logger.debug(f"Suggested context: {suggested}")
        
        return query, info
    
    def generate_response(
        self,
        base_response: str,
        intent: str,
        results_count: int,
        result_type: str = "candidates",
        session_id: Optional[str] = None
    ) -> str:
        """
        Generate natural, varied response using ResponseVariator.
        
        Args:
            base_response: Raw response from response_generator
            intent: User's detected intent
            results_count: Number of results returned
            result_type: Type of results ("candidates", "skills", etc.)
            session_id: Session ID for context (optional)
        
        Returns:
            Natural, varied response text
        """
        
        # Determine response context based on intent and session state
        context = ResponseContext.FIRST_SEARCH  # default
        
        if session_id:
            conv_context = self.get_or_create_context(session_id)
            if len(conv_context.turn_history) > 0:
                # Determine context from preprocessing info
                # This is a simplified mapping - can be more sophisticated
                context = ResponseContext.FOLLOW_UP
        
        # If no results, use special no-results response
        if results_count == 0:
            return self.response_variator.create_no_match_response(
                criteria=result_type
            )
        
        # Generate varied response
        varied_response = self.response_variator.generate_response(
            context=context,
            result_type=result_type,
            count=results_count
        )
        
        return varied_response
    
    def record_turn(
        self,
        session_id: str,
        user_query: str,
        bot_response: str,
        intent: str,
        entities: Dict,
        results: list,
        preprocessing_info: Dict
    ) -> None:
        """
        Record a conversation turn in context.
        
        Args:
            session_id: Conversation session ID
            user_query: Original user query
            bot_response: Bot's response
            intent: Detected intent
            entities: Extracted entities
            results: Query results
            preprocessing_info: From preprocess_query()
        """
        context = self.get_or_create_context(session_id)
        
        # Infer conversation theme from intent
        theme = self._infer_theme_from_intent(intent)
        if theme:
            context.conversation_theme = theme
        
        # Add turn to history
        context.add_turn(
            user_query=user_query,
            detected_intent=intent,
            extracted_entities=entities,
            bot_response=bot_response
        )
        
        # Update context based on results
        if results:
            context.last_search_results = [
                r if isinstance(r, dict) else r.__dict__ for r in results
            ]
            
            # If results have candidates, set current candidate
            if intent == "profile" and results:
                first_result = results[0]
                name = (first_result.get('name') if isinstance(first_result, dict)
                       else getattr(first_result, 'name', None))
                if name:
                    context.set_current_candidate({
                        'name': name,
                        'data': first_result
                    })
        
        # Extract and add search filters if this was a search intent
        if intent == "search":
            filters = self._extract_filters_from_entities(entities)
            for filter_type, value in filters.items():
                if filter_type == "skills":
                    context.add_search_filter(skills=value if isinstance(value, list) else [value])
                elif filter_type == "locations":
                    context.add_search_filter(locations=value if isinstance(value, list) else [value])
                elif filter_type == "seniority":
                    context.add_search_filter(seniority_level=value)
                elif filter_type == "experience":
                    context.add_search_filter(experience_min=value)
        
        logger.debug(f"Recorded turn {len(context.turn_history)} for session {session_id}")
    
    def get_context_summary(self, session_id: str) -> Dict:
        """
        Get human-readable summary of conversation context.
        
        Returns:
            {
                "conversation_theme": "hiring_search",
                "current_candidate": "John Doe",
                "active_filters": {...},
                "turns_count": 3,
                "last_query": "...",
                "last_results_count": 5
            }
        """
        context = self.get_or_create_context(session_id)
        
        return {
            "conversation_theme": context.conversation_theme.value if context.conversation_theme else None,
            "current_candidate": context.current_candidate.get('name') if context.current_candidate else None,
            "active_filters": {
                "skills": context.active_filters.skills,
                "locations": context.active_filters.locations,
                "experience_min": context.active_filters.experience_min,
                "seniority_level": context.active_filters.seniority_level
            },
            "turns_count": len(context.turn_history),
            "last_query": context.turn_history[-1].user_query if context.turn_history else None,
            "last_results_count": len(context.last_search_results) if context.last_search_results else 0
        }
    
    def clear_session(self, session_id: str) -> None:
        """Clear session context"""
        if session_id in self.contexts:
            del self.contexts[session_id]
            logger.info(f"Cleared conversation context for session: {session_id}")
    
    # Private helpers
    
    def _infer_theme_from_intent(self, intent: str) -> Optional[ConversationTheme]:
        """Map intent to conversation theme"""
        mapping = {
            "search": ConversationTheme.HIRING_SEARCH,
            "profile": ConversationTheme.DETAILED_PROFILE,
            "compare": ConversationTheme.COMPARISON,
            "skills": ConversationTheme.SKILL_DISCOVERY,
            "portfolio": ConversationTheme.PORTFOLIO_REVIEW,
        }
        return mapping.get(intent)
    
    def _extract_filters_from_entities(self, entities: Dict) -> Dict:
        """Extract search filters from extracted entities"""
        filters = {}
        
        if "skills" in entities and entities["skills"]:
            filters["skills"] = entities["skills"]
        if "locations" in entities and entities["locations"]:
            filters["locations"] = entities["locations"]
        if "seniority" in entities and entities["seniority"]:
            filters["seniority"] = entities["seniority"]
        if "experience" in entities and entities["experience"]:
            filters["experience"] = entities["experience"]
        
        return filters
