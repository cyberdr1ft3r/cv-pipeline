"""
Intent Detection Module
Detects user's intent from natural language query
"""

import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class IntentDetector:
    """
    Detect user's intent from natural language query.
    
    Intent types:
    - conversation: General free-form discussion
    - profile: Tell me about X
    - search: Find candidates with X
    - comparison: Compare X and Y
    - ranking: Show top N
    - gap_analysis: What skills missing
    - recommendation: Who should we hire
    - filter: Multi-criteria search
    - aggregation: Count/average stats
    """
    
    INTENT_PATTERNS = {
        "conversation": [
            r"^(?:hello|hi|hey|greetings?|how are you|what's up|sup)\b",
            # French greetings
            r"^(?:bonjour|salut|coucou|allo|allô)\b",
            r"^(?:je veux|je voudrais).*(?:parler|discuter|communiquer)",
            # List all patterns (English & French)
            r"^(?:list|show|give me).*(?:all|everything|tout)",
            r"^(?:donne moi|donner moi|montre moi|affiche).*(?:tout|tous|la liste)",
            r"^(?:donnees?|données?)",
            # Tell me about patterns
            r"tell me about.*our.*(?:data|candidates|company|team|system)",
            r"(?:what|tell me).*(?:specific|topics?|things?|subjects?|areas?).*(?:discuss|talk|chat|explore)",
            r"(?:what|which).*(?:can you help|topics?|areas?|things?)\s+(?:with|about)",
            r"explain.*(?:this|that|the|your)",
            r"can you.*(?:help|assist|explain|discuss)",
            r"(?:let's|let us).*(?:talk|discuss|chat)",
            r"i'd like to.*(?:talk|discuss|chat|learn)",
            r"(?:general|open).*(?:discussion|chat|conversation)",
            r"^(?:ok|okay|alright|sure|yes)$",
            r"(?:overview|introduction|general info)",
            # Topic inquiry patterns - asking about available data/capabilities
            r"^(?:profiles?|candidates?|skills?|data|experience|education)$",
            r"^(?:what|tell).*(?:about|in)\s+(?:profiles?|candidates?|our|the)",
            r"^(?:what|show).*(?:topics?|subjects?|things?).*(?:available|do you have)",
            # Data inquiry patterns - full database access
            r"^(?:what|which).*(?:skills?|locations?|data|candidates?|information)",
            r"^(?:how many|total|count)",
            r"^(?:tell me about).*(?:database|data|system|capabilities)",
            r"^(?:what can|can i|can you)",
            r"^(?:statistics?|stats|summary|overview)",
            # Follow-up and conversational continuers
            r"^(?:and|but|also|plus|furthermore)\s+",
            r"(?:tell me more|more about|what else|anything else|more details?|elaborate)",
            r"^(?:okay|ok|thanks?|thank you|got it|understood|i see)\b",
            r"(?:so|then|now|next|after that)",
            r"(?:that's|that is|it's|it is).*(?:interesting|cool|good|useful|helpful)",
        ],
        "profile": [
            r"tell me about\s+(.+)",
            r"who is\s+(.+)",
            r"(?:show|get|display).*profile.*(?:of|for)?\s*(.+)",
            r"get info.*(?:on|about)?\s*(.+)",
            r"(?:background|details?|information).*(?:on|about)?\s*(.+)",
            r"(?:candidate|person)\s+(.+)",
        ],
        "search": [
            r"find.*(?:with|having)\s+(.+)",
            r"who has\s+(.+)",
            r"candidates?.*(?:with|having).*(.+)",
            r"search.*(.+)",
            r"look for.*(.+)",
            r"(?:show|display|list).*(?:candidates?|people)\s+(?:with|who have)\s+(.+)",
        ],
        "comparison": [
            r"compare\s+(.+?)\s+(?:and|vs|with)\s+(.+)",
            r"how.*(.+?).*compare.*(?:to|with).*(.+)",
            r"(?:difference|differences?|diff)\s+(?:between|among).*(.+?)\s+(?:and|vs|with)\s+(.+)",
        ],
        "ranking": [
            r"top\s+(\d+)",
            r"(?:show|list|display).*ranking",
            r"best candidates?",
            r"rank.*by",
            r"highest.*score",
        ],
        "gap_analysis": [
            r"(?:what|which).*(?:missing|lacking|gap|weak|weakness)",
            r"gaps?\s+(?:for|in).*(.+)",
            r"skills?.*(?:missing|lacking|needed)",
            r"weakness.*(.+)",
        ],
        "recommendation": [
            r"who should we hire",
            r"best fit",
            r"recommend",
            r"suggest.*candidate",
            r"(?:ideal|perfect|best).*candidate",
        ],
        "filter": [
            r"from\s+(.+)\s+with\s+(.+)",
            r"where.*(.+)",
            r"(?:candidates?|people).*(?:from|in).*(.+)\s+(?:with|who have).*(.+)",
        ],
        "aggregation": [
            r"how many\s+(.+)",
            r"count.*(.+)",
            r"average.*(.+)",
            r"(?:statistics|stats|summary)",
        ]
    }
    
    def __init__(self, llm_client=None):
        """
        Initialize intent detector
        
        Args:
            llm_client: LLM client for fallback intent detection
        """
        self.llm = llm_client
    
    def detect(
        self,
        query: str,
        conversation_history: List = None
    ) -> Dict:
        """
        Detect intent from query with context awareness.
        
        Returns:
            {
                "type": "profile" | "search" | "conversation" | ...,
                "confidence": 0.95,
                "matched_pattern": "tell me about",
                "groups": ("John Doe",),
                "method": "pattern" | "context" | "llm"
            }
        """
        
        query_lower = query.lower().strip()
        
        # Check conversation context - if previous intent was "conversation",
        # short queries should stay as conversation (topic inquiry)
        if self._should_maintain_conversation(query, conversation_history):
            logger.debug(f"Maintaining conversation mode based on context")
            return {
                "type": "conversation",
                "confidence": 0.85,
                "matched_pattern": "context_continuation",
                "groups": [],
                "method": "context"
            }
        
        # Try pattern matching first (fast)
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    logger.debug(f"Pattern matched: {intent_type} - {pattern}")
                    return {
                        "type": intent_type,
                        "confidence": 0.9,
                        "matched_pattern": pattern,
                        "groups": match.groups() if match.groups() else [],
                        "method": "pattern"
                    }
        
        # Fall back to LLM if available
        if self.llm:
            logger.debug("Falling back to LLM for intent detection")
            return self._detect_with_llm(query)
        
        # Default to search if no pattern matched
        logger.warning(f"No intent pattern matched for: {query}")
        return {
            "type": "search",
            "confidence": 0.5,
            "matched_pattern": None,
            "groups": [],
            "method": "default"
        }
    
    def _should_maintain_conversation(self, query: str, history: List = None) -> bool:
        """
        Check if query should maintain conversation mode based on context.
        
        After a conversation opener (like "what topics can we discuss?"),
        short single-word queries are likely topic inquiries, not searches.
        """
        if not history or len(history) < 2:
            return False
        
        # Check if previous turn was conversation
        previous_turn = history[-1]
        if isinstance(previous_turn, dict) and previous_turn.get('intent') != 'conversation':
            return False
        
        # Short queries (1-2 words) after conversation are likely topic inquiries
        query_words = query.lower().strip().split()
        if len(query_words) > 3:
            return False
        
        # Keywords that are data topics, not searches
        topic_keywords = {
            'profiles', 'profile', 'candidates', 'candidate', 'skills', 'skill',
            'data', 'experience', 'education', 'projects', 'project',
            'certifications', 'certification', 'achievements', 'achievement',
            'languages', 'language', 'tools', 'tool', 'frameworks', 'framework'
        }
        
        if any(word in topic_keywords for word in query_words):
            logger.debug(f"Detected topic inquiry continuation: {query}")
            return True
        
        return False
    
    def _detect_with_llm(self, query: str) -> Dict:
        """Detect intent using LLM"""
        
        prompt = f"""Analyze this query and determine the user's intent.

Query: "{query}"

Intent types (choose ONE):
- conversation: General discussion, asking about topics or capabilities
- profile: User wants info about specific person
- search: User wants to find candidates by criteria
- comparison: User wants to compare candidates
- ranking: User wants ranked list
- gap_analysis: User wants to know missing skills
- recommendation: User wants hiring recommendations
- filter: User wants multi-criteria search
- aggregation: User wants statistics

Return ONLY the intent type name, nothing else. Example: "profile"
        """
        
        try:
            response = self.llm.generate(prompt)
            intent = response.strip().lower().split()[0]
            
            # Validate intent
            valid_intents = [
                "conversation", "profile", "search", "comparison", "ranking",
                "gap_analysis", "recommendation", "filter", "aggregation"
            ]
            
            if intent not in valid_intents:
                intent = "search"
            
            logger.debug(f"LLM detected intent: {intent}")
            
            return {
                "type": intent,
                "confidence": 0.7,
                "matched_pattern": None,
                "groups": [],
                "method": "llm"
            }
        except Exception as e:
            logger.error(f"Error in LLM intent detection: {str(e)}")
            return {
                "type": "search",
                "confidence": 0.5,
                "matched_pattern": None,
                "groups": [],
                "method": "error"
            }
