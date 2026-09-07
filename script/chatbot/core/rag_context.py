"""
RAG Context Manager
Implements Retrieval-Augmented Generation workflow:
1. Vectorize user input
2. Search all databases for similarity
3. Collect relevant information
4. Build LLM context with retrieved data
"""

import logging
import json
from typing import List, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class RAGContextManager:
    """Manages RAG workflow - retrieval, enrichment, and context building"""
    
    def __init__(self, semantic_search, vectorizer, cache=None):
        """
        Initialize RAG context manager
        
        Args:
            semantic_search: SemanticSearch instance for retrieval
            vectorizer: Vectorizer instance for embeddings
            cache: Optional cache for storing context
        """
        self.semantic_search = semantic_search
        self.vectorizer = vectorizer
        self.cache = cache
        logger.info("✓ RAGContextManager initialized")
    
    def retrieve_context(
        self,
        query: str,
        limit_per_table: int = 5,
        similarity_threshold: float = 0.25
    ) -> Dict[str, Any]:
        """
        STEP 1: Retrieve COMPLETE context from ALL database tables
        Uses UNIVERSAL search - scans every table, every text column
        
        Args:
            query: User query
            limit_per_table: Max results per table
            similarity_threshold: Minimum similarity score
        
        Returns:
            Dictionary with complete retrieved context from all tables
        """
        try:
            logger.info(f"RAG: Retrieving COMPLETE context from ALL tables for: {query[:60]}")
            
            # Check cache first
            cache_key = f"rag_context:{query}"
            if self.cache:
                try:
                    cached = self.cache.get(cache_key)
                    if cached:
                        logger.debug("Retrieved context from cache")
                        return cached
                except:
                    pass  # Cache miss or error, continue with retrieval
            
            # Perform UNIVERSAL semantic search across ALL database tables
            search_results = self.semantic_search.search_all_tables_universal(
                query,
                limit_per_table=limit_per_table,
                threshold=similarity_threshold
            )
            
            # Build context with ALL retrieved information from ALL tables
            context = {
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "retrieved_data": search_results,
                "retrieval_stats": {
                    "total_tables_searched": len(self.semantic_search.table_schemas),
                    "tables_with_results": len(search_results),
                    "total_results_found": sum(len(v) for v in search_results.values()),
                    "similarity_threshold": similarity_threshold
                }
            }
            
            # Cache the context
            if self.cache:
                self.cache.set(cache_key, context, ttl=300)
            
            logger.info(f"Context retrieved: {context['retrieval_stats']}")
            return context
        
        except Exception as e:
            logger.error(f"Error retrieving RAG context: {str(e)}")
            return {
                "query": query,
                "retrieved_data": {},
                "error": str(e)
            }
    
    def build_llm_context_prompt(self, retrieved_context: Dict[str, Any]) -> str:
        """
        STEP 2: Build TRULY DYNAMIC context prompt
        Structure depends entirely on what tables and data were found
        No static format - adapts to whatever data exists
        
        Args:
            retrieved_context: Context retrieved from databases
        
        Returns:
            Dynamically formatted prompt based on actual data
        """
        try:
            prompt_parts = []
            retrieved_data = retrieved_context.get("retrieved_data", {})
            
            if not retrieved_data:
                logger.warning("No retrieved data to build context from")
                return ""
            
            # Dynamically process each table found
            for table_name, results in retrieved_data.items():
                if not results:
                    continue
                
                prompt_parts.append(f"\n## DATA FROM {table_name.upper()}\n")
                
                for i, result in enumerate(results, 1):
                    # Get similarity score
                    score = result.get('score', 'N/A')
                    prompt_parts.append(f"\n### Match {i} (Score: {score})\n")
                    
                    # Get the row data
                    row = result.get('row', {})
                    
                    # Display all fields in the row
                    for field_name, field_value in row.items():
                        if field_value is not None and field_value != "":
                            # Format the value nicely
                            if isinstance(field_value, (list, dict)):
                                prompt_parts.append(f"- {field_name}: {str(field_value)[:200]}\n")
                            else:
                                value_str = str(field_value)[:300]  # Cap at 300 chars
                                prompt_parts.append(f"- {field_name}: {value_str}\n")
            
            # Add search statistics
            stats = retrieved_context.get("retrieval_stats", {})
            if stats:
                prompt_parts.append("\n## SEARCH INFORMATION\n")
                prompt_parts.append(f"- Total tables searched: {stats.get('total_tables_searched', 0)}\n")
                prompt_parts.append(f"- Tables with matching results: {stats.get('tables_with_results', 0)}\n")
                prompt_parts.append(f"- Total results found: {stats.get('total_results_found', 0)}\n")
                prompt_parts.append(f"- Similarity threshold used: {stats.get('similarity_threshold', 0)}\n")
            
            context_prompt = "".join(prompt_parts)
            logger.debug(f"Built DYNAMIC LLM context prompt ({len(context_prompt)} chars) from {len(retrieved_data)} tables")
            return context_prompt
        
        except Exception as e:
            logger.error(f"Error building LLM context: {str(e)}")
            return ""
    
    def enrich_llm_prompt(self, user_prompt: str, retrieved_context: Dict[str, Any]) -> str:
        """
        STEP 3: Combine user prompt with retrieved context for LLM
        
        Args:
            user_prompt: Original user query
            retrieved_context: Context retrieved from databases
        
        Returns:
            Enriched prompt for LLM
        """
        try:
            context_prompt = self.build_llm_context_prompt(retrieved_context)
            
            # Build system context
            system_context = """You are an intelligent candidate and recruitment assistant. 
You have access to a database of candidates with their skills and experiences.
Use the provided context (RELEVANT CANDIDATES, SKILLS, EXPERIENCES) to provide accurate, 
helpful responses about candidates and recruitment-related queries.

Always:
1. Reference specific candidates or skills when relevant
2. Provide match percentages or similarity scores when available
3. Answer in a conversational, human-like manner
4. Be honest about what data is available
5. Suggest candidates or skills that match user requirements when applicable
"""
            
            # Combine system context, retrieved context, and user prompt
            enriched_prompt = f"""{system_context}

{context_prompt}

USER QUERY: {user_prompt}

Please respond naturally, using the provided candidate and skill data to inform your answer."""
            
            logger.debug(f"Enriched prompt with context ({len(enriched_prompt)} chars total)")
            return enriched_prompt
        
        except Exception as e:
            logger.error(f"Error enriching LLM prompt: {str(e)}")
            return user_prompt
    
    def cache_search_result(self, query: str, result: Dict[str, Any], ttl: int = 300):
        """
        Cache a search result for future reference
        
        Args:
            query: The search query
            result: The search result
            ttl: Time to live in seconds
        """
        if not self.cache:
            return
        
        try:
            cache_key = f"search_result:{query}"
            self.cache.set(cache_key, result, ttl=ttl)
            logger.debug(f"Cached search result for: {query[:50]}")
        except Exception as e:
            logger.debug(f"Failed to cache result: {str(e)}")
    
    def get_cached_search_result(self, query: str) -> Dict[str, Any] | None:
        """
        Retrieve cached search result if available
        
        Args:
            query: The search query
        
        Returns:
            Cached result or None if not found
        """
        if not self.cache:
            return None
        
        try:
            cache_key = f"search_result:{query}"
            result = self.cache.get(cache_key)
            if result:
                logger.debug(f"Retrieved cached result for: {query[:50]}")
            return result
        except Exception as e:
            logger.debug(f"Failed to retrieve cached result: {str(e)}")
            return None
    
    def clear_context_cache(self):
        """Clear all cached RAG contexts"""
        if not self.cache:
            return
        
        try:
            # Clear all RAG-related cache entries
            keys_to_delete = []
            for key in self.cache.data.keys():
                if key.startswith("rag_context:") or key.startswith("search_result:"):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache.data[key]
            
            logger.info(f"Cleared {len(keys_to_delete)} RAG cache entries")
        except Exception as e:
            logger.debug(f"Error clearing cache: {str(e)}")
