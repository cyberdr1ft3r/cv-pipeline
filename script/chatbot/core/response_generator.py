"""
Response Generator Module
Generates natural language responses from query results
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """
    Generate natural language responses from query results.
    Uses LLM to create conversational, contextual responses.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize response generator
        
        Args:
            llm_client: LLM client for generating responses
        """
        self.llm = llm_client
    
    def generate(
        self,
        intent: str,
        query_results: Dict,
        entities: Dict,
        context: Dict,
        stream: bool = False
    ) -> Dict:
        """
        Generate response from query results.
        
        Returns:
            {
                "response": "John Doe is a Senior Backend...",
                "sources": [...],
                "confidence": 0.95
            }
        """
        
        data = query_results.get("data", [])
        
        if not data:
            return {
                "response": self._generate_no_results_response(intent, entities),
                "sources": [],
                "confidence": 0.8
            }
        
        try:
            # Summarize data for LLM
            data_summary = self._summarize_data(data, intent)
            
            # Generate response with LLM or fallback
            if self.llm:
                response_text = self._generate_with_llm(
                    intent, data_summary, query_results, entities, context
                )
            else:
                response_text = self._generate_fallback(data, intent)
            
            return {
                "response": response_text,
                "sources": self._extract_sources(data),
                "confidence": 0.9
            }
        
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "response": f"I encountered an error generating a response: {str(e)}",
                "sources": [],
                "confidence": 0.5
            }
    
    def _summarize_data(self, data: List[Dict], intent: str) -> str:
        """Summarize query results for LLM"""
        
        if intent == "profile":
            return self._summarize_profile(data)
        elif intent == "ranking":
            return self._summarize_ranking(data)
        elif intent == "comparison":
            return self._summarize_comparison(data)
        elif intent == "search":
            return self._summarize_search(data)
        elif intent == "gap_analysis":
            return self._summarize_gap_analysis(data)
        elif intent == "filter":
            return self._summarize_filter(data)
        elif intent == "aggregation":
            return self._summarize_aggregation(data)
        else:
            return json.dumps(data[:5], indent=2, default=str)
    
    def _summarize_profile(self, data: List[Dict]) -> str:
        """Summarize single candidate profile"""
        if not data:
            return ""
        
        candidate = data[0]
        
        summary = f"""
Candidate Information:
- Name: {candidate.get('candidate_name', 'Unknown')}
- Email: {candidate.get('email', 'N/A')}
- Location: {candidate.get('location', 'N/A')}
- Experience: {candidate.get('years_experience', 'N/A')} years
- Skills: {', '.join(candidate.get('skills', [])) if candidate.get('skills') else 'Not specified'}
- Test Score: {candidate.get('overall_score', 'N/A')}/100
- Final Match Score: {candidate.get('final_score', 'N/A')}/100
- Rank: {candidate.get('rank', 'N/A')}
        """
        return summary
    
    def _summarize_ranking(self, data: List[Dict]) -> str:
        """Summarize top candidates ranking"""
        summary = "Top Candidates (by match score):\n"
        
        for i, candidate in enumerate(data[:10], 1):
            summary += f"\n{i}. {candidate.get('candidate_name', 'Unknown')}\n"
            summary += f"   Score: {candidate.get('final_score', 'N/A')}/100\n"
            summary += f"   Location: {candidate.get('location', 'N/A')}\n"
            summary += f"   Experience: {candidate.get('years_experience', 'N/A')} years\n"
        
        return summary
    
    def _summarize_comparison(self, data: List[Dict]) -> str:
        """Summarize candidate comparison"""
        summary = "Candidate Comparison:\n"
        
        for candidate in data[:2]:
            summary += f"\n{candidate.get('candidate_name', 'Unknown')}:\n"
            summary += f"  - Match Score: {candidate.get('final_score', 'N/A')}/100\n"
            summary += f"  - Experience: {candidate.get('years_experience', 'N/A')} years\n"
            summary += f"  - Location: {candidate.get('location', 'N/A')}\n"
            summary += f"  - Skills: {', '.join(candidate.get('skills', []))[:100]}\n"
        
        return summary
    
    def _summarize_search(self, data: List[Dict]) -> str:
        """Summarize search results"""
        summary = f"Found {len(data)} candidates:\n"
        
        for candidate in data[:5]:
            summary += f"\n- {candidate.get('candidate_name', 'Unknown')}\n"
            summary += f"  Score: {candidate.get('final_score', 'N/A')}/100\n"
            summary += f"  Location: {candidate.get('location', 'N/A')}\n"
        
        if len(data) > 5:
            summary += f"\n... and {len(data) - 5} more"
        
        return summary
    
    def _summarize_gap_analysis(self, data: List[Dict]) -> str:
        """Summarize gap analysis"""
        summary = "Skill Gaps Analysis:\n"
        
        for candidate in data[:3]:
            summary += f"\n{candidate.get('candidate_name', 'Unknown')}:\n"
            summary += f"  - Current Skills: {', '.join(candidate.get('skills', []))[:80]}\n"
            summary += f"  - Match Score: {candidate.get('final_score', 'N/A')}/100\n"
        
        return summary
    
    def _summarize_filter(self, data: List[Dict]) -> str:
        """Summarize filtered results"""
        summary = f"Filtered results: {len(data)} candidates\n"
        
        for candidate in data[:5]:
            summary += f"\n- {candidate.get('candidate_name', 'Unknown')}\n"
            summary += f"  Location: {candidate.get('location', 'N/A')}\n"
            summary += f"  Experience: {candidate.get('years_experience', 'N/A')} years\n"
            summary += f"  Score: {candidate.get('final_score', 'N/A')}/100\n"
        
        return summary
    
    def _summarize_aggregation(self, data: List[Dict]) -> str:
        """Summarize aggregation results"""
        if not data:
            return ""
        
        summary = "Statistics:\n"
        
        stats = data[0]
        for key, value in stats.items():
            if value is not None:
                if isinstance(value, float):
                    summary += f"- {key}: {value:.2f}\n"
                else:
                    summary += f"- {key}: {value}\n"
        
        return summary
    
    def _generate_with_llm(
        self,
        intent: str,
        data_summary: str,
        query_results: Dict,
        entities: Dict,
        context: Dict
    ) -> str:
        """Generate response using LLM"""
        
        prompt = f"""You are a helpful HR assistant analyzing candidate data.

Based on this data:
{data_summary}

User's Intent: {intent}

Generate a natural, conversational response that:
1. Directly answers the user's question
2. Includes specific numbers and facts from the data
3. Highlights key insights
4. Is concise but informative (2-4 sentences)
5. Uses natural language without unnecessary formatting

Response:
        """
        
        try:
            response = self.llm.generate(prompt)
            logger.debug(f"Generated response via LLM")
            return response.strip()
        
        except Exception as e:
            logger.error(f"Error generating with LLM: {str(e)}")
            return self._generate_fallback(query_results.get("data", []), intent)
    
    def _generate_fallback(self, data: List[Dict], intent: str) -> str:
        """Generate response without LLM"""
        
        if intent == "profile":
            if data:
                c = data[0]
                return (f"{c.get('candidate_name', 'This candidate')} is located in "
                       f"{c.get('location', 'an unspecified location')} with "
                       f"{c.get('years_experience', 'unknown')} years of experience. "
                       f"Match score: {c.get('final_score', 'N/A')}/100")
        
        elif intent == "ranking":
            return (f"Found {len(data)} candidates. "
                   f"Top candidate is {data[0].get('candidate_name', 'Unknown')} "
                   f"with score {data[0].get('final_score', 'N/A')}/100.")
        
        elif intent == "comparison":
            if len(data) >= 2:
                c1, c2 = data[0], data[1]
                return (f"{c1.get('candidate_name')} (score: {c1.get('final_score')}) "
                       f"vs {c2.get('candidate_name')} (score: {c2.get('final_score')}). "
                       f"{c1.get('candidate_name')} ranks higher.")
        
        elif intent == "search":
            return (f"Found {len(data)} candidates matching your criteria. "
                   f"Top match: {data[0].get('candidate_name', 'Unknown')} "
                   f"with score {data[0].get('final_score', 'N/A')}/100.")
        
        return f"Found {len(data)} results matching your query."
    
    def _generate_no_results_response(self, intent: str, entities: Dict) -> str:
        """Generate response when no results found"""
        
        if intent == "profile":
            name = entities.get("candidates", ["that candidate"])[0]
            return f"I couldn't find a candidate named '{name}' in the database."
        
        elif intent == "search":
            skills = entities.get("skills", [])
            if skills:
                return f"No candidates found with {', '.join(skills)} skills."
            return "No candidates found matching your criteria."
        
        elif intent == "filter":
            return "No candidates match the specified criteria."
        
        return "I couldn't find any matching results for your query."
    
    def _extract_sources(self, data: List[Dict]) -> List[str]:
        """Extract candidate names as sources"""
        sources = []
        for item in data:
            name = item.get('candidate_name')
            if name:
                sources.append(name)
        return sources
