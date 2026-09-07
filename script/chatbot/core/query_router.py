"""
Query Router Module
Routes queries to appropriate data sources and builds combined queries
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class QueryRouter:
    """
    Route query to appropriate data sources.
    Can use SQL for exact filtering, Vector search for semantic, or combined.
    """
    
    def __init__(self, db_session, chroma_client=None, cache=None):
        """
        Initialize query router
        
        Args:
            db_session: SQLite database session
            chroma_client: Chroma vector DB client
            cache: Cache instance
        """
        self.db = db_session
        self.chroma = chroma_client
        self.cache = cache
    
    def route(
        self,
        intent: str,
        entities: Dict,
        context: Dict,
        original_query: str
    ) -> Dict:
        """
        Route query based on intent and return results.
        
        Returns:
            {
                "data": [...],
                "sources": ["sql", "vector"],
                "count": 10,
                "query_type": "profile"
            }
        """
        
        logger.info(f"Routing query with intent: {intent}")
        
        try:
            if intent == "profile":
                return self._handle_profile(entities, context)
            elif intent == "search":
                return self._handle_search(entities, context)
            elif intent == "comparison":
                return self._handle_comparison(entities, context)
            elif intent == "ranking":
                return self._handle_ranking(entities, context)
            elif intent == "gap_analysis":
                return self._handle_gap_analysis(entities, context)
            elif intent == "filter":
                return self._handle_filter(entities, context)
            elif intent == "aggregation":
                return self._handle_aggregation(entities, context)
            else:
                logger.warning(f"Unknown intent: {intent}")
                return {"data": [], "sources": [], "error": f"Unknown intent: {intent}"}
        
        except Exception as e:
            logger.error(f"Error routing query: {str(e)}", exc_info=True)
            return {"data": [], "sources": [], "error": str(e)}
    
    def _handle_profile(self, entities: Dict, context: Dict) -> Dict:
        """Get single candidate profile"""
        
        if not entities.get("candidates"):
            return {"data": [], "error": "No candidate specified", "sources": []}
        
        candidate_name = entities["candidates"][0]
        
        # Check cache
        if self.cache:
            cache_key = f"candidate_profile_{candidate_name}"
            cached = self.cache.get(cache_key)
            if cached:
                data = json.loads(cached) if isinstance(cached, str) else cached
                logger.debug(f"Cache hit for {candidate_name}")
                return {"data": [data], "sources": ["cache"], "count": 1}
        
        # Query database
        try:
            query = """
            SELECT c.*, 
                   fr.final_score, fr.rank
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            WHERE c.candidate_name LIKE ?
            LIMIT 1
            """
            
            result = self.db.execute(query, [f"%{candidate_name}%"]).fetchone()
            
            if result:
                data = dict(result)
                
                # Cache for 1 hour
                if self.cache:
                    self.cache.set(
                        f"candidate_profile_{candidate_name}",
                        json.dumps(data, default=str),
                        ttl=3600
                    )
                
                logger.debug(f"Found candidate: {candidate_name}")
                return {"data": [data], "sources": ["sql"], "count": 1}
            
            logger.warning(f"Candidate not found: {candidate_name}")
            return {"data": [], "error": f"Candidate {candidate_name} not found", "sources": []}
        
        except Exception as e:
            logger.error(f"Error in profile query: {str(e)}")
            return {"data": [], "error": str(e), "sources": []}
    
    def _handle_search(self, entities: Dict, context: Dict) -> Dict:
        """Search for candidates by skills or criteria"""
        
        if not entities.get("skills"):
            return {"data": [], "error": "No skills specified", "sources": []}
        
        try:
            # Build SQL query for skill search
            skill_list = entities["skills"]
            
            # Use technologies table for skill matching
            conditions = []
            params = []
            
            for skill in skill_list:
                conditions.append("t.tech_name LIKE ?")
                params.append(f"%{skill}%")
            
            where_clause = " OR ".join(conditions) if conditions else "1=1"
            
            query = f"""
            SELECT DISTINCT c.*, fr.final_score
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            LEFT JOIN technologies t ON c.id = t.candidate_id
            WHERE {where_clause}
            ORDER BY fr.final_score DESC
            LIMIT 20
            """
            
            results = self.db.execute(query, params).fetchall()
            data = [dict(row) for row in results]
            
            logger.debug(f"Found {len(data)} candidates with skills: {skill_list}")
            
            return {
                "data": data,
                "sources": ["sql"],
                "count": len(data),
                "query_type": "search"
            }
        
        except Exception as e:
            logger.error(f"Error in search query: {str(e)}")
            return {"data": [], "error": str(e), "sources": []}
    
    def _handle_comparison(self, entities: Dict, context: Dict) -> Dict:
        """Compare two candidates"""
        
        candidates = entities.get("candidates", [])
        
        if len(candidates) < 2:
            return {"data": [], "error": "Need at least 2 candidates to compare", "sources": []}
        
        try:
            results = []
            
            for name in candidates[:2]:  # Compare only first 2
                query = """
                SELECT c.*, 
                       fr.final_score, fr.rank
                FROM candidates c
                LEFT JOIN final_results fr ON c.id = fr.candidate_id
                WHERE c.candidate_name LIKE ?
                LIMIT 1
                """
                
                result = self.db.execute(query, [f"%{name}%"]).fetchone()
                if result:
                    results.append(dict(result))
            
            logger.debug(f"Comparing {len(results)} candidates")
            
            return {
                "data": results,
                "sources": ["sql"],
                "count": len(results),
                "query_type": "comparison"
            }
        
        except Exception as e:
            logger.error(f"Error in comparison query: {str(e)}")
            return {"data": [], "error": str(e), "sources": []}
    
    def _handle_ranking(self, entities: Dict, context: Dict) -> Dict:
        """Get top N candidates"""
        
        limit = 10
        if entities.get("numbers"):
            limit = min(entities["numbers"][0], 50)  # Cap at 50
        
        try:
            query = """
            SELECT c.*, fr.final_score, fr.rank
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            ORDER BY COALESCE(fr.final_score, 0) DESC
            LIMIT ?
            """
            
            results = self.db.execute(query, [limit]).fetchall()
            data = [dict(row) for row in results]
            
            logger.debug(f"Ranked {len(data)} candidates")
            
            return {
                "data": data,
                "sources": ["sql"],
                "count": len(data),
                "query_type": "ranking"
            }
        
        except Exception as e:
            logger.error(f"Error in ranking query: {str(e)}")
            return {"data": [], "error": str(e), "sources": []}
    
    def _handle_gap_analysis(self, entities: Dict, context: Dict) -> Dict:
        """Analyze skill gaps"""
        
        candidate_name = None
        if entities.get("candidates"):
            candidate_name = entities["candidates"][0]
        
        try:
            if candidate_name:
                # Gap analysis for specific candidate
                query = """
                SELECT c.*, fr.final_score
                FROM candidates c
                LEFT JOIN final_results fr ON c.id = fr.candidate_id
                WHERE c.candidate_name LIKE ?
                LIMIT 1
                """
                
                result = self.db.execute(query, [f"%{candidate_name}%"]).fetchone()
                if result:
                    return {
                        "data": [dict(result)],
                        "sources": ["sql"],
                        "query_type": "gap_analysis",
                        "analysis_type": "specific"
                    }
            
            # General gap analysis - top candidates with gaps
            query = """
            SELECT c.*, fr.final_score
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            ORDER BY fr.final_score DESC
            LIMIT 10
            """
            
            results = self.db.execute(query).fetchall()
            data = [dict(row) for row in results]
            
            return {
                "data": data,
                "sources": ["sql"],
                "count": len(data),
                "query_type": "gap_analysis",
                "analysis_type": "general"
            }
        
        except Exception as e:
            logger.error(f"Error in gap analysis query: {str(e)}")
            return {"data": [], "error": str(e), "sources": []}
    
    def _handle_filter(self, entities: Dict, context: Dict) -> Dict:
        """Multi-criteria filtering"""
        
        try:
            where_clauses = []
            params = []
            
            # Location filter
            if entities.get("locations"):
                locations = entities["locations"]
                placeholders = ",".join("?" * len(locations))
                where_clauses.append(f"c.location IN ({placeholders})")
                params.extend(locations)
            
            # Experience filter
            if entities.get("time_range"):
                tr = entities["time_range"]
                if tr.get("value"):
                    where_clauses.append("c.years_experience >= ?")
                    params.append(tr["value"])
            
            # Score filter
            if entities.get("scores"):
                sc = entities["scores"]
                if sc.get("min"):
                    where_clauses.append("ts.overall_score >= ?")
                    params.append(sc["min"])
                if sc.get("max"):
                    where_clauses.append("ts.overall_score <= ?")
                    params.append(sc["max"])
            
            # Skills filter
            if entities.get("skills"):
                skill_conditions = []
                for skill in entities["skills"]:
                    skill_conditions.append("c.skills LIKE ?")
                    params.append(f"%{skill}%")
                where_clauses.append("(" + " OR ".join(skill_conditions) + ")")
            
            where = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            query = f"""
            SELECT c.*, fr.final_score
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            WHERE {where}
            ORDER BY COALESCE(fr.final_score, 0) DESC
            LIMIT 50
            """
            
            results = self.db.execute(query, params).fetchall()
            data = [dict(row) for row in results]
            
            logger.debug(f"Filter query returned {len(data)} results")
            
            return {
                "data": data,
                "sources": ["sql"],
                "count": len(data),
                "query_type": "filter"
            }
        
        except Exception as e:
            logger.error(f"Error in filter query: {str(e)}")
            return {"data": [], "error": str(e), "sources": []}
    
    def _handle_aggregation(self, entities: Dict, context: Dict) -> Dict:
        """Handle statistical aggregation queries"""
        
        try:
            if entities.get("skills"):
                # Count candidates with skill
                skill = entities["skills"][0]
                query = """
                SELECT COUNT(*) as count, ? as skill
                FROM candidates
                WHERE skills LIKE ?
                """
                
                result = self.db.execute(query, [skill, f"%{skill}%"]).fetchone()
                return {
                    "data": [dict(result)] if result else [],
                    "sources": ["sql"],
                    "query_type": "aggregation",
                    "aggregation_type": "skill_count"
                }
            
            # Overall statistics
            query = """
            SELECT 
                COUNT(*) as total_candidates,
                AVG(years_experience) as avg_experience,
                AVG(fr.final_score) as avg_score
            FROM candidates c
            LEFT JOIN final_results fr ON c.id = fr.candidate_id
            """
            
            result = self.db.execute(query).fetchone()
            return {
                "data": [dict(result)] if result else [],
                "sources": ["sql"],
                "query_type": "aggregation",
                "aggregation_type": "overall_stats"
            }
        
        except Exception as e:
            logger.error(f"Error in aggregation query: {str(e)}")
            return {"data": [], "error": str(e), "sources": []}
