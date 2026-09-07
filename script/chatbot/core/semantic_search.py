"""
Semantic Search Module
Searches ALL tables in database dynamically for relevant information
"""

import logging
import sqlite3
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SemanticSearch:
    """Performs semantic search across ALL database tables dynamically"""
    
    def __init__(self, db_path: str, vectorizer, cache=None):
        """
        Initialize semantic search
        
        Args:
            db_path: Path to SQLite database
            vectorizer: Vectorizer instance for embeddings
            cache: Optional cache for storing search results
        """
        self.db_path = db_path
        self.vectorizer = vectorizer
        self.cache = cache
        self.embedding_cache = {}
        self.table_schemas = self._scan_database_schema()
        logger.info(f"✓ SemanticSearch initialized - Found {len(self.table_schemas)} tables")
        for table_name, columns in self.table_schemas.items():
            logger.info(f"  Table: {table_name} - Text columns: {columns}")
    
    def _scan_database_schema(self) -> Dict[str, List[str]]:
        """
        Dynamically scan database to find all tables and their text columns
        
        Returns:
            Dict mapping table name -> list of text column names
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            table_schemas = {}
            for (table_name,) in tables:
                if table_name.startswith('sqlite_'):
                    continue
                
                # Get column info for this table
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                # Filter for text-like columns (TEXT, VARCHAR, etc.)
                text_columns = []
                for col in columns:
                    col_name = col[1]
                    col_type = col[2].upper() if col[2] else ""
                    # Include TEXT, VARCHAR, and other text-like types
                    if any(t in col_type for t in ['TEXT', 'CHAR', 'CLOB', 'JSON']):
                        text_columns.append(col_name)
                
                if text_columns:
                    table_schemas[table_name] = text_columns
            
            conn.close()
            return table_schemas
        
        except Exception as e:
            logger.error(f"Error scanning database schema: {str(e)}")
            return {}
    
    def _extract_candidate_names(self, query: str) -> List[str]:
        """
        Extract potential candidate names from query text
        Looks for capitalized name patterns (First Last)
        
        Args:
            query: Search query
        
        Returns:
            List of potential candidate names found
        """
        # Pattern: Capital letter followed by space and another capital letter(s)
        # Also matches names with multiple parts (e.g., "El Houssaine")
        pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]*)+)'
        matches = re.findall(pattern, query)
        return matches

    def _search_table_semantic(
        self,
        table_name: str,
        text_columns: List[str],
        query_vector: List[float],
        limit: int = 5,
        threshold: float = 0.25,
        candidate_names: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantically search a specific table for matches
        
        Args:
            table_name: Name of the table to search
            text_columns: List of text columns in this table
            query_vector: Vectorized query
            limit: Max results from this table
            threshold: Minimum similarity
            candidate_names: Optional list of candidate names to boost relevance
        
        Returns:
            List of matching rows with similarity scores
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all rows from this table
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return []
            
            # Build search vectors by combining text from all text columns
            row_vectors = []
            for row in rows:
                row_dict = dict(row)
                
                # Combine all text columns into one searchable text
                combined_text = " ".join([
                    str(row_dict.get(col, "")) 
                    for col in text_columns 
                    if row_dict.get(col)
                ])
                
                if not combined_text.strip():
                    continue
                
                # Create unique identifier for this row
                pk_val = row_dict.get('id', row_dict.get('candidate_id', hash(str(row_dict))))
                cache_key = f"table_vec:{table_name}:{pk_val}"
                
                if cache_key in self.embedding_cache:
                    vec = self.embedding_cache[cache_key]
                else:
                    vec = self.vectorizer.vectorize(combined_text)
                    self.embedding_cache[cache_key] = vec
                
                # For candidate-related tables, boost relevance if candidate name is mentioned
                candidate_boost = 1.0
                if candidate_names and table_name in ['candidates', 'candidate_profiles', 'education', 'technologies', 'certifications', 'projects']:
                    for cand_name in candidate_names:
                        if cand_name.lower() in combined_text.lower():
                            candidate_boost = 1.5  # Boost matches with mentioned candidates
                            break
                
                row_vectors.append((
                    f"{table_name}:{pk_val}",
                    vec,
                    {
                        "table": table_name,
                        "row": row_dict,
                        "combined_text": combined_text,
                        "candidate_boost": candidate_boost
                    }
                ))
            
            # Find similar rows
            similar = self.vectorizer.find_most_similar(
                query_vector,
                [(rid, rvec) for rid, rvec, _ in row_vectors],
                top_k=limit * 2,  # Get more candidates to filter with boost
                threshold=threshold
            )
            
            # Apply candidate name boost to similarity scores
            boosted_results = []
            for sim in similar:
                for rid, rvec, data in row_vectors:
                    if rid == sim["id"]:
                        boosted_sim = sim.copy()
                        # Apply boost to similarity score
                        original_score = boosted_sim.get("similarity", 0)
                        boosted_sim["similarity"] = min(1.0, original_score * data["candidate_boost"])
                        boosted_results.append({
                            **boosted_sim,
                            "table": table_name,
                            "row": data["row"],
                            "combined_text": data["combined_text"]
                        })
                        break
            
            # Sort by boosted similarity and limit
            boosted_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            results = boosted_results[:limit]
            
            return results
        
        except Exception as e:
            logger.error(f"Error searching table {table_name}: {str(e)}")
            return []
    
    def search_all_tables_universal(
        self,
        query: str,
        limit_per_table: int = 5,
        threshold: float = 0.25
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        UNIVERSAL search: Scan ALL tables in database for query matches
        Automatically finds and searches every table with text data
        NO hardcoded tables - works with any database schema
        
        For comparison queries, extracts candidate names and boosts their relevance
        
        Args:
            query: Search query
            limit_per_table: Max results per table
            threshold: Minimum similarity threshold
        
        Returns:
            Dictionary with results from each table found
        """
        try:
            logger.info(f"UNIVERSAL SEARCH: Querying all {len(self.table_schemas)} tables for: {query[:60]}")
            
            # Extract candidate names from query for targeted search
            candidate_names = self._extract_candidate_names(query)
            if candidate_names:
                logger.info(f"  Extracted candidate names: {candidate_names}")
            
            # Vectorize the query once
            query_vector = self.vectorizer.vectorize(query)
            
            # Search each table
            all_results = {}
            for table_name, text_columns in self.table_schemas.items():
                table_results = self._search_table_semantic(
                    table_name,
                    text_columns,
                    query_vector,
                    limit=limit_per_table,
                    threshold=threshold,
                    candidate_names=candidate_names
                )
                
                if table_results:
                    all_results[table_name] = table_results
                    logger.info(f"  {table_name}: Found {len(table_results)} matches")
            
            total_results = sum(len(v) for v in all_results.values())
            logger.info(f"UNIVERSAL SEARCH completed: {total_results} total results from {len(all_results)} tables")
            
            return all_results
        
        except Exception as e:
            logger.error(f"Error in universal search: {str(e)}")
            return {}
    
    def clear_embedding_cache(self):
        """Clear the embedding cache to free memory"""
        self.embedding_cache.clear()
        logger.debug("Embedding cache cleared")
