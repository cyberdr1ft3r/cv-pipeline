"""
Response Variator
=================

Generates varied, natural response phrasings instead of repetitive templates.

Instead of always saying:
  "I found X candidates with Y skills"

Use natural variations:
  "Great! I found X candidates"
  "Interesting combination - X candidates match"
  "That brings it down to X candidates"
  "I've got X strong matches"
  "Looking for X type? Here are X candidates"

This makes the chatbot feel more human-like and less robotic.
"""

import random
from typing import Dict, List, Any, Optional
from enum import Enum


class ResponseContext(Enum):
    """Context for response generation"""
    FIRST_SEARCH = "first_search"  # Initial query
    REFINEMENT = "refinement"  # Narrowing down previous results
    EXPANSION = "expansion"  # Getting more results
    FOLLOW_UP = "follow_up"  # Related to previous conversation
    COMPARISON = "comparison"  # Comparing candidates
    DETAIL_REQUEST = "detail_request"  # Asking for more info
    NO_RESULTS = "no_results"  # No matches found
    CLARIFICATION = "clarification"  # Asking for clarification


class ResponseVariator:
    """
    Generates varied response phrasings based on context.
    
    Maintains a mental model of:
    - What was searched before
    - How many results were found
    - Whether results are narrowing down or expanding
    - Conversation tone/style
    """
    
    def __init__(self):
        self.response_templates = self._build_templates()
        self.last_response_template = None  # Track to avoid repetition
    
    @staticmethod
    def _build_templates() -> Dict[str, Dict[str, List[str]]]:
        """Build template library for different contexts"""
        return {
            ResponseContext.FIRST_SEARCH.value: {
                "found_results": [
                    "I found {count} candidates with {criteria}.",
                    "Great! {count} candidates match {criteria}.",
                    "Looking for {criteria}? I have {count} candidates.",
                    "{count} candidates fit {criteria}.",
                    "Perfect! I found {count} strong matches for {criteria}.",
                ],
                "no_results": [
                    "No candidates found with {criteria}.",
                    "Hmm, I didn't find anyone with {criteria}.",
                    "That's a specific combination - no exact matches.",
                    "I couldn't find candidates with {criteria}.",
                ],
                "follow_up": [
                    "Want me to show you:",
                    "Should I also look at:",
                    "Would you like to see:",
                    "Are you interested in:",
                ]
            },
            ResponseContext.REFINEMENT.value: {
                "narrowing_down": [
                    "Narrowing it down to {criteria}, that's {count} candidates.",
                    "Adding {criteria} filter... that brings it down to {count}.",
                    "With {criteria} added, I get {count} candidates.",
                    "Filtering by {criteria}: {count} candidates remain.",
                    "That combination gives me {count} candidates.",
                ],
                "same_results": [
                    "All {count} candidates still match.",
                    "Interestingly, all {count} still qualify.",
                    "The refinement doesn't change the results - still {count}.",
                ]
            },
            ResponseContext.EXPANSION.value: {
                "more_results": [
                    "I also found {count} more candidates.",
                    "There are {count} additional matches.",
                    "Beyond those, {count} other candidates qualify.",
                    "If we expand the search: {count} more candidates.",
                ],
                "no_more_results": [
                    "Those are all the candidates matching {criteria}.",
                    "No additional matches available.",
                    "That's the complete list.",
                ]
            },
            ResponseContext.COMPARISON.value: {
                "direct_comparison": [
                    "{name1} vs {name2}:",
                    "Comparing {name1} and {name2}:",
                    "Here's how {name1} compares to {name2}:",
                    "{name1} vs {name2} - strengths and gaps:",
                ],
                "group_comparison": [
                    "Here's how they compare:",
                    "Comparing all {count} candidates:",
                    "The {count} candidates rank as:",
                ]
            },
            ResponseContext.DETAIL_REQUEST.value: {
                "profile_intro": [
                    "{name} - {title}",
                    "Meet {name}, {title}",
                    "{name}: {title}",
                    "Here's {name}'s profile - {title}",
                ],
                "highlight_skills": [
                    "Key strengths:",
                    "{name}'s top skills:",
                    "What {name} excels at:",
                    "Standout qualifications:",
                ],
                "follow_up_detail": [
                    "What would you like to know more about?",
                    "Anything else you'd like to know?",
                    "Should I dive deeper into any area?",
                    "Want more details on specific skills?",
                ]
            },
            ResponseContext.NO_RESULTS.value: {
                "offer_alternatives": [
                    "No exact matches, but I found {count} candidates with {similar}.",
                    "That's specific - {count} candidates have {similar}.",
                    "I don't have an exact match, but {count} candidates have {similar}.",
                    "Close alternatives: {count} candidates with {similar}.",
                ],
                "ask_clarification": [
                    "Can I clarify what you're looking for?",
                    "Would you like me to adjust the criteria?",
                    "Should I relax any of the filters?",
                    "Would a broader search help?",
                ]
            },
            ResponseContext.CLARIFICATION.value: {
                "confirm_understanding": [
                    "So you're looking for {criteria}?",
                    "If I understand correctly: {criteria}",
                    "Just to confirm: {criteria}",
                    "Let me make sure: {criteria}",
                ],
                "provide_options": [
                    "I can search for:",
                    "Would any of these work:",
                    "Should I look at:",
                ]
            }
        }
    
    def generate_response(
        self,
        context: ResponseContext,
        result_type: str,
        count: Optional[int] = None,
        criteria: Optional[str] = None,
        name: Optional[str] = None,
        title: Optional[str] = None,
        similar: Optional[str] = None,
        previous_count: Optional[int] = None
    ) -> str:
        """
        Generate a response with natural variation.
        
        Args:
            context: Response context (what type of response)
            result_type: Type of result (e.g., "found_results", "narrowing_down")
            count: Number of results
            criteria: Search criteria used
            name: Candidate name (for detail responses)
            title: Candidate title
            similar: Similar criteria (for alternatives)
            previous_count: Previous result count (for comparison)
        
        Returns:
            Natural language response string
        """
        templates = self.response_templates.get(context.value, {}).get(result_type, [])
        
        if not templates:
            return f"Found {count} candidates." if count else "Search complete."
        
        # Select a template (avoid last one used)
        template = self._select_template(templates)
        
        # Format template with provided data
        response = template.format(
            count=count or 0,
            criteria=criteria or "criteria",
            name=name or "candidate",
            title=title or "professional",
            similar=similar or "related skills",
            previous=previous_count or 0
        )
        
        return response
    
    def _select_template(self, templates: List[str]) -> str:
        """Select a template, avoiding repetition"""
        if len(templates) == 1:
            return templates[0]
        
        # Try to avoid selecting same template twice in a row
        available = templates
        if self.last_response_template and self.last_response_template in templates:
            available = [t for t in templates if t != self.last_response_template]
        
        selected = random.choice(available)
        self.last_response_template = selected
        return selected
    
    def build_response(
        self,
        main_message: str,
        follow_up_options: Optional[List[str]] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Build a complete response with main message + options.
        
        Args:
            main_message: Primary response
            follow_up_options: Optional list of suggested follow-ups
            additional_context: Optional additional information
        
        Returns:
            Complete formatted response
        """
        response = main_message
        
        if additional_context:
            response += f"\n{additional_context}"
        
        if follow_up_options:
            # Add follow-up suggestions
            response += "\n\n"
            follow_up_intro = random.choice([
                "Would you also like to:",
                "Should I also look at:",
                "Want me to show you:",
                "Interested in:"
            ])
            response += follow_up_intro + "\n"
            for i, option in enumerate(follow_up_options, 1):
                response += f"  • {option}\n"
        
        return response
    
    def create_natural_intro(
        self,
        intent: str,
        result_count: int,
        previous_results: Optional[int] = None
    ) -> str:
        """
        Create a natural introduction based on intent and result trend.
        
        Args:
            intent: Type of search (search, filter, ranking, etc.)
            result_count: Current number of results
            previous_results: Previous number of results (if narrowing/expanding)
        
        Returns:
            Natural introduction string
        """
        if intent == "search" and not previous_results:
            return self.generate_response(
                ResponseContext.FIRST_SEARCH,
                "found_results",
                count=result_count
            )
        
        elif intent == "filter" and previous_results:
            if result_count < previous_results:
                context = ResponseContext.REFINEMENT
                result_type = "narrowing_down"
            elif result_count > previous_results:
                context = ResponseContext.EXPANSION
                result_type = "more_results"
            else:
                context = ResponseContext.REFINEMENT
                result_type = "same_results"
            
            return self.generate_response(context, result_type, count=result_count)
        
        elif intent == "ranking":
            return f"Here are the {result_count} top candidates ranked by match score:"
        
        else:
            return f"Found {result_count} candidates."
    
    def create_no_match_response(
        self,
        criteria: str,
        alternative_count: Optional[int] = None,
        alternative_criteria: Optional[str] = None
    ) -> str:
        """
        Create empathetic response when no matches found.
        
        Args:
            criteria: What was searched for
            alternative_count: Number of relaxed search results
            alternative_criteria: What was found instead
        
        Returns:
            Empathetic response with helpful alternatives
        """
        if alternative_count and alternative_count > 0:
            return self.generate_response(
                ResponseContext.NO_RESULTS,
                "offer_alternatives",
                count=alternative_count,
                similar=alternative_criteria or "related skills"
            )
        else:
            return self.generate_response(
                ResponseContext.NO_RESULTS,
                "ask_clarification"
            )
    
    def create_confirmation(self, query: str, criteria: str) -> str:
        """Create confirmation of understood query"""
        confirmations = [
            f"Just to confirm: {criteria}",
            f"So you're looking for {criteria}",
            f"If I understand correctly, you want {criteria}",
            f"Let me make sure: {criteria}",
        ]
        return random.choice(confirmations)
    
    def get_conversation_tone_hint(self) -> str:
        """Get hint for conversation tone (friendly, professional, etc.)"""
        tones = [
            "friendly",
            "professional",
            "helpful",
            "conversational"
        ]
        return random.choice(tones)
