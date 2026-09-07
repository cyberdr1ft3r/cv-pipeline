"""
Pronoun Resolver
================

Resolves pronouns and implicit references to actual entities based on conversation context.

Handles:
- Personal pronouns: he, she, they, it
- Demonstratives: this, that, these, those
- Implied references: "them", "both", "either"
- Context-based resolution: "the previous one", "the top candidate"

Example:
  User: "Show me Bahaddou El Houssaine"
  System: Sets current_candidate = Bahaddou
  
  User: "Does he have Docker?"
  Resolver: Recognizes "he" → Bahaddou
  Query becomes: "Does Bahaddou have Docker?"
"""

import re
from typing import Dict, Optional, List, Any
from enum import Enum


class PronounType(Enum):
    """Types of pronouns and references"""
    PERSONAL_SINGULAR = "personal_singular"  # he, she, it
    PERSONAL_PLURAL = "personal_plural"  # they, them
    DEMONSTRATIVE = "demonstrative"  # this, that, these, those
    RELATIVE = "relative"  # who, which, that (in relative clauses)
    POSSESSIVE = "possessive"  # his, her, their, its
    IMPLICIT = "implicit"  # "both", "either", previous results


class PronounResolver:
    """
    Resolves pronouns to actual entities from conversation context.
    
    Uses:
    - Conversation history
    - Current candidate
    - Previous search results
    - Entity tracking (skills, locations mentioned)
    """
    
    # Pronoun patterns
    PRONOUNS = {
        # Personal (singular)
        'he': PronounType.PERSONAL_SINGULAR,
        'she': PronounType.PERSONAL_SINGULAR,
        'it': PronounType.PERSONAL_SINGULAR,
        
        # Personal (plural)
        'they': PronounType.PERSONAL_PLURAL,
        'them': PronounType.PERSONAL_PLURAL,
        
        # Demonstrative
        'this': PronounType.DEMONSTRATIVE,
        'that': PronounType.DEMONSTRATIVE,
        'these': PronounType.DEMONSTRATIVE,
        'those': PronounType.DEMONSTRATIVE,
        
        # Possessive
        'his': PronounType.POSSESSIVE,
        'her': PronounType.POSSESSIVE,
        'their': PronounType.POSSESSIVE,
        'its': PronounType.POSSESSIVE,
        
        # Implicit
        'both': PronounType.IMPLICIT,
        'either': PronounType.IMPLICIT,
        'one': PronounType.IMPLICIT,
    }
    
    def __init__(self):
        self.pronouns_pattern = re.compile(
            r'\b(' + '|'.join(self.PRONOUNS.keys()) + r')\b',
            re.IGNORECASE
        )
    
    def resolve_pronouns(
        self,
        query: str,
        current_candidate: Optional[Dict[str, Any]] = None,
        last_search_results: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[str]] = None
    ) -> str:
        """
        Resolve all pronouns in query to actual entities.
        
        Args:
            query: User query potentially containing pronouns
            current_candidate: Currently discussed candidate
            last_search_results: Results from previous search
            conversation_history: Recent conversation turns
        
        Returns:
            Query with pronouns resolved to actual entity names/references
        """
        resolved_query = query
        
        # Find all pronouns in query
        pronouns_found = self._find_pronouns(query)
        
        if not pronouns_found:
            return resolved_query
        
        # Resolve each pronoun
        for pronoun_match in pronouns_found:
            pronoun = pronoun_match.group(0).lower()
            resolved_reference = self._resolve_single_pronoun(
                pronoun,
                current_candidate=current_candidate,
                last_search_results=last_search_results,
                conversation_history=conversation_history
            )
            
            if resolved_reference:
                # Replace pronoun with resolved reference
                # Use case-insensitive replacement
                resolved_query = re.sub(
                    r'\b' + pronoun + r'\b',
                    resolved_reference,
                    resolved_query,
                    flags=re.IGNORECASE,
                    count=1
                )
        
        return resolved_query
    
    def _find_pronouns(self, query: str) -> List:
        """Find all pronouns in query"""
        return list(self.pronouns_pattern.finditer(query))
    
    def _resolve_single_pronoun(
        self,
        pronoun: str,
        current_candidate: Optional[Dict[str, Any]] = None,
        last_search_results: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[str]] = None
    ) -> Optional[str]:
        """Resolve single pronoun to actual entity"""
        pronoun_lower = pronoun.lower()
        pronoun_type = self.PRONOUNS.get(pronoun_lower)
        
        if pronoun_type == PronounType.PERSONAL_SINGULAR:
            # Singular pronoun → likely refers to current candidate
            if current_candidate:
                return current_candidate.get("candidate_name")
        
        elif pronoun_type == PronounType.PERSONAL_PLURAL:
            # Plural pronoun → likely refers to previous results
            if last_search_results and len(last_search_results) > 0:
                # Return reference to "the candidates" or "previous results"
                return f"the {len(last_search_results)} candidates"
        
        elif pronoun_type == PronounType.DEMONSTRATIVE:
            # "this", "that" → depends on context
            if current_candidate:
                return current_candidate.get("candidate_name")
            elif last_search_results:
                return f"the {len(last_search_results)} results"
        
        elif pronoun_type == PronounType.POSSESSIVE:
            # "his", "her", "their" → similar to personal pronouns
            if current_candidate:
                candidate_name = current_candidate.get("candidate_name")
                # Return possessive form context
                return f"{candidate_name}'s"
        
        elif pronoun_type == PronounType.IMPLICIT:
            # "both", "either" → reference to multiple things
            if last_search_results and len(last_search_results) >= 2:
                return f"the {len(last_search_results)} candidates"
        
        return None
    
    def has_pronouns(self, query: str) -> bool:
        """Check if query contains pronouns"""
        return bool(self.pronouns_pattern.search(query))
    
    def get_resolution_confidence(
        self,
        query: str,
        current_candidate: Optional[Dict[str, Any]] = None,
        last_search_results: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """
        Estimate confidence in pronoun resolution.
        
        Returns:
            0.0 (no pronouns) to 1.0 (high confidence resolution)
        """
        if not self.has_pronouns(query):
            return 1.0  # No pronouns = perfect resolution
        
        confidence = 0.5  # Start with base confidence
        
        # Increase if current candidate exists
        if current_candidate:
            confidence += 0.3
        
        # Increase if previous results exist
        if last_search_results and len(last_search_results) > 0:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def extract_pronoun_references(self, query: str) -> Dict[str, str]:
        """
        Extract which pronouns are used and what they likely refer to.
        
        Returns:
            Dict mapping pronouns to their likely referents
        """
        references = {}
        pronouns_found = self._find_pronouns(query)
        
        for pronoun_match in pronouns_found:
            pronoun = pronoun_match.group(0).lower()
            if pronoun not in references:  # Avoid duplicates
                pronoun_type = self.PRONOUNS[pronoun]
                references[pronoun] = {
                    "type": pronoun_type.value,
                    "likely_refers_to": self._describe_pronoun_referent(pronoun_type)
                }
        
        return references
    
    @staticmethod
    def _describe_pronoun_referent(pronoun_type: PronounType) -> str:
        """Describe what a pronoun type likely refers to"""
        descriptions = {
            PronounType.PERSONAL_SINGULAR: "current candidate",
            PronounType.PERSONAL_PLURAL: "previous search results",
            PronounType.DEMONSTRATIVE: "current context (candidate or results)",
            PronounType.POSSESSIVE: "possession relation to candidate",
            PronounType.RELATIVE: "relative clause antecedent",
            PronounType.IMPLICIT: "multiple items from context",
        }
        return descriptions.get(pronoun_type, "unknown")


class ImplicitReferenceResolver:
    """
    Handles more complex implicit references beyond pronouns.
    
    Examples:
    - "Compare them" → them = previous results
    - "The top one" → the top result
    - "Others like him" → other candidates similar to current candidate
    - "The first three" → first three from results
    """
    
    def resolve_implicit_references(
        self,
        query: str,
        current_candidate: Optional[Dict[str, Any]] = None,
        last_search_results: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Resolve implicit references like 'the top one', 'the others', etc."""
        resolved = query
        
        # "the top one" → top candidate
        if re.search(r'\btop\s+(one|candidate|match)', query, re.IGNORECASE):
            if last_search_results:
                top_name = last_search_results[0].get("candidate_name", "the top candidate")
                resolved = re.sub(
                    r'\btop\s+(one|candidate|match)',
                    top_name,
                    resolved,
                    flags=re.IGNORECASE
                )
        
        # "the others" → other candidates
        if re.search(r'\bthe\s+others', query, re.IGNORECASE):
            if last_search_results and len(last_search_results) > 1:
                other_count = len(last_search_results) - 1
                resolved = resolved.replace(
                    "the others",
                    f"the {other_count} other candidates"
                )
        
        # "all of them" → all previous results
        if re.search(r'\ball\s+of\s+them', query, re.IGNORECASE):
            if last_search_results:
                resolved = resolved.replace(
                    "all of them",
                    f"all {len(last_search_results)} candidates"
                )
        
        return resolved
