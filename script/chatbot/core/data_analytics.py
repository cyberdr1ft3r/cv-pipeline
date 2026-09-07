"""
Data Analytics Module
=====================

Provides full visibility into candidate database.
Enables comprehensive conversational access to all data.
No artificial limitations - full database visibility.
"""

import logging
from typing import Dict, List, Any, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class DataAnalytics:
    """
    Comprehensive data analytics and visibility layer.
    Provides insights into the full candidate database.
    """
    
    def __init__(self, db_session):
        """Initialize with database session"""
        self.db = db_session
        self._cache = {}
    
    def get_candidate_count(self) -> int:
        """Get total number of candidates"""
        try:
            result = self.db.execute("SELECT COUNT(*) as count FROM candidates").fetchone()
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error getting candidate count: {str(e)}")
            return 0
    
    def get_all_candidates(self, limit: int = None) -> List[Dict]:
        """Get all candidates with optional limit"""
        try:
            query = """
            SELECT c.*, fr.final_score, fr.rank
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            ORDER BY fr.final_score DESC
            """
            if limit:
                query += f" LIMIT {limit}"
            
            results = self.db.execute(query).fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting all candidates: {str(e)}")
            return []
    
    def get_candidates_by_skill(self, skill: str) -> List[Dict]:
        """Get all candidates with a specific skill"""
        try:
            query = """
            SELECT DISTINCT c.*, fr.final_score, fr.rank
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            LEFT JOIN technologies t ON c.id = t.candidate_id
            WHERE t.tech_name LIKE ?
            ORDER BY fr.final_score DESC
            """
            
            results = self.db.execute(query, [f"%{skill}%"]).fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting candidates by skill: {str(e)}")
            return []
    
    def get_all_skills(self) -> List[str]:
        """Get all unique skills in database"""
        try:
            query = "SELECT DISTINCT tech_name FROM technologies ORDER BY tech_name"
            results = self.db.execute(query).fetchall()
            return [row['tech_name'] for row in results]
        except Exception as e:
            logger.error(f"Error getting all skills: {str(e)}")
            return []
    
    def get_skill_distribution(self) -> Dict[str, int]:
        """Get count of candidates per skill"""
        try:
            query = """
            SELECT t.tech_name, COUNT(DISTINCT t.candidate_id) as count
            FROM technologies t
            GROUP BY t.tech_name
            ORDER BY count DESC
            """
            
            results = self.db.execute(query).fetchall()
            return {row['tech_name']: row['count'] for row in results}
        except Exception as e:
            logger.error(f"Error getting skill distribution: {str(e)}")
            return {}
    
    def get_top_candidates(self, limit: int = 10) -> List[Dict]:
        """Get top ranked candidates"""
        try:
            query = """
            SELECT c.*, fr.final_score, fr.rank
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            ORDER BY fr.final_score DESC, c.candidate_name ASC
            LIMIT ?
            """
            
            results = self.db.execute(query, [limit]).fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting top candidates: {str(e)}")
            return []
    
    def get_candidate_names(self) -> List[str]:
        """Get all candidate names"""
        try:
            query = "SELECT DISTINCT candidate_name FROM candidates ORDER BY candidate_name"
            results = self.db.execute(query).fetchall()
            return [row['candidate_name'] for row in results]
        except Exception as e:
            logger.error(f"Error getting candidate names: {str(e)}")
            return []
    
    def get_candidates_by_location(self, location: str) -> List[Dict]:
        """Get candidates from a specific location"""
        try:
            query = """
            SELECT c.*, fr.final_score, fr.rank
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            WHERE c.location LIKE ?
            ORDER BY fr.final_score DESC
            """
            
            results = self.db.execute(query, [f"%{location}%"]).fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting candidates by location: {str(e)}")
            return []
    
    def get_all_locations(self) -> List[str]:
        """Get all unique locations"""
        try:
            query = "SELECT DISTINCT location FROM candidates WHERE location IS NOT NULL ORDER BY location"
            results = self.db.execute(query).fetchall()
            return [row['location'] for row in results if row['location']]
        except Exception as e:
            logger.error(f"Error getting all locations: {str(e)}")
            return []
    
    def search_candidates(self, query_text: str) -> List[Dict]:
        """Search candidates by name or keyword"""
        try:
            search_term = f"%{query_text}%"
            query = """
            SELECT c.*, fr.final_score, fr.rank
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            WHERE c.candidate_name LIKE ? 
               OR c.email LIKE ?
               OR c.phone LIKE ?
            ORDER BY fr.final_score DESC
            """
            
            results = self.db.execute(query, [search_term, search_term, search_term]).fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error searching candidates: {str(e)}")
            return []
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get comprehensive summary statistics"""
        try:
            total_candidates = self.get_candidate_count()
            top_skills = self.get_skill_distribution()
            all_locations = self.get_all_locations()
            
            # Get average score
            avg_query = "SELECT AVG(final_score) as avg_score FROM final_results"
            avg_result = self.db.execute(avg_query).fetchone()
            avg_score = avg_result['avg_score'] if avg_result else 0
            
            return {
                'total_candidates': total_candidates,
                'average_score': round(avg_score, 2) if avg_score else 0,
                'total_skills': len(top_skills),
                'total_locations': len(all_locations),
                'top_skills': dict(list(top_skills.items())[:5]),  # Top 5 skills
                'locations': all_locations
            }
        except Exception as e:
            logger.error(f"Error getting summary stats: {str(e)}")
            return {}
    
    def get_candidates_list_formatted(self, candidates: List[Dict]) -> str:
        """Format candidate list for display"""
        if not candidates:
            return "No candidates found."
        
        lines = []
        for i, c in enumerate(candidates, 1):
            name = c.get('candidate_name', 'Unknown')
            score = c.get('final_score', 'N/A')
            lines.append(f"{i}. {name} (Score: {score})")
        
        return "\n".join(lines)
    
    def get_skills_list_formatted(self, skills: Dict[str, int]) -> str:
        """Format skills list for display"""
        if not skills:
            return "No skills found."
        
        lines = []
        for skill, count in sorted(skills.items(), key=lambda x: x[1], reverse=True)[:20]:
            lines.append(f"• {skill} ({count} candidates)")
        
        return "\n".join(lines)
