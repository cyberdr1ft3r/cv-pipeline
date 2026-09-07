"""
Entity Extraction Module
Extracts structured entities from natural language queries
"""

import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class EntityExtractor:
    """Extract structured entities from natural language"""
    
    # Common skills database
    COMMON_SKILLS = [
        "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Cloud",
        "React", "Vue", "Angular", "Django", "FastAPI", "Flask", "Spring",
        "PostgreSQL", "MongoDB", "Redis", "MySQL", "SQLite", "Cassandra",
        "DevOps", "CI/CD", "Microservices", "REST APIs", "GraphQL",
        "Machine Learning", "AI", "Data Science", "Big Data", "Spark",
        "Linux", "Git", "Jenkins", "Docker", "Terraform"
    ]
    
    # Common locations
    COMMON_LOCATIONS = [
        "Paris", "London", "New York", "Berlin", "Tokyo", "Singapore",
        "San Francisco", "Dubai", "Montreal", "Toronto", "Sydney",
        "Amsterdam", "Barcelona", "Rome", "Madrid", "Moscow"
    ]
    
    def __init__(self, db_session=None):
        """
        Initialize entity extractor
        
        Args:
            db_session: Database session for candidate lookup
        """
        self.db = db_session
    
    def extract(
        self,
        query: str,
        intent: str,
        context: Dict = None
    ) -> Dict:
        """
        Extract entities relevant to the intent.
        
        Returns:
            {
                "candidates": ["John Doe"],
                "skills": ["Docker", "Python"],
                "locations": ["Paris"],
                "numbers": [5],
                "scores": {"min": 80, "max": 100},
                "time_range": {"value": 5, "unit": "years"},
                "criteria": {}
            }
        """
        
        context = context or {}
        
        entities = {
            "candidates": [],
            "skills": [],
            "locations": [],
            "numbers": [],
            "scores": None,
            "time_range": None,
            "criteria": {}
        }
        
        # Extract candidate names
        entities["candidates"] = self._extract_candidate_names(query, context)
        
        # Extract skills
        entities["skills"] = self._extract_skills(query)
        
        # Extract locations
        entities["locations"] = self._extract_locations(query)
        
        # Extract numbers
        entities["numbers"] = self._extract_numbers(query)
        
        # Extract score ranges
        entities["scores"] = self._extract_score_range(query)
        
        # Extract time ranges
        entities["time_range"] = self._extract_time_range(query)
        
        logger.debug(f"Extracted entities for '{query[:50]}...': {entities}")
        
        return entities
    
    def _extract_candidate_names(self, query: str, context: Dict) -> List[str]:
        """Extract candidate names from query"""
        
        matches = []
        
        # Handle pronouns from context
        if context:
            if "he " in query.lower() and context.get('last_candidate'):
                matches.append(context['last_candidate'])
            
            if "she " in query.lower() and context.get('last_candidate'):
                matches.append(context['last_candidate'])
            
            if "them" in query.lower() and context.get('recent_candidates'):
                matches.extend(context['recent_candidates'][:2])
        
        # Pattern: "John Doe", "Jane Smith", etc.
        # Capitalized words that are not at start of sentence
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        
        for match in re.finditer(pattern, query):
            name = match.group(1)
            # Simple check: names have at least 2 words
            if len(name.split()) >= 2:
                matches.append(name)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_matches = []
        for name in matches:
            if name not in seen:
                unique_matches.append(name)
                seen.add(name)
        
        logger.debug(f"Extracted candidate names: {unique_matches}")
        return unique_matches
    
    def _extract_skills(self, query: str) -> List[str]:
        """Extract skill names from query"""
        
        found_skills = []
        
        for skill in self.COMMON_SKILLS:
            if re.search(rf'\b{re.escape(skill)}\b', query, re.IGNORECASE):
                found_skills.append(skill)
        
        logger.debug(f"Extracted skills: {found_skills}")
        return found_skills
    
    def _extract_locations(self, query: str) -> List[str]:
        """Extract location names"""
        
        found = []
        
        for loc in self.COMMON_LOCATIONS:
            if re.search(rf'\b{loc}\b', query, re.IGNORECASE):
                found.append(loc)
        
        logger.debug(f"Extracted locations: {found}")
        return found
    
    def _extract_numbers(self, query: str) -> List[int]:
        """Extract numbers (for rankings, scores, etc.)"""
        
        numbers = re.findall(r'\b(\d+)\b', query)
        result = [int(n) for n in numbers]
        
        logger.debug(f"Extracted numbers: {result}")
        return result
    
    def _extract_score_range(self, query: str) -> Optional[Dict]:
        """Extract score ranges like '80-90', 'above 85'"""
        
        # Pattern: "80-90", "80 to 90"
        range_match = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)', query)
        if range_match:
            result = {
                "min": int(range_match.group(1)),
                "max": int(range_match.group(2))
            }
            logger.debug(f"Extracted score range: {result}")
            return result
        
        # Pattern: "above 85", "below 80"
        above_match = re.search(r'above\s+(\d+)', query, re.IGNORECASE)
        if above_match:
            result = {"min": int(above_match.group(1))}
            logger.debug(f"Extracted score range (above): {result}")
            return result
        
        below_match = re.search(r'below\s+(\d+)', query, re.IGNORECASE)
        if below_match:
            result = {"max": int(below_match.group(1))}
            logger.debug(f"Extracted score range (below): {result}")
            return result
        
        return None
    
    def _extract_time_range(self, query: str) -> Optional[Dict]:
        """Extract time ranges like '5+ years'"""
        
        match = re.search(r'(\d+)\+?\s*(years?|months?|days?)', query, re.IGNORECASE)
        if match:
            result = {
                "value": int(match.group(1)),
                "unit": match.group(2).lower()
            }
            logger.debug(f"Extracted time range: {result}")
            return result
        
        return None
