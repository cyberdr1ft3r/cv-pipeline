"""
Vectorizer Module
Converts text data to vector embeddings using sentence-transformers
"""

import logging
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np
import sqlite3

logger = logging.getLogger(__name__)


class Vectorizer:
    """Vectorizes text data and manages embeddings"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the vectorizer with a sentence-transformers model
        
        Args:
            model_name: Name of the sentence-transformers model to use
        """
        try:
            self.model = SentenceTransformer(model_name)
            self.model_name = model_name
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"✓ Vectorizer initialized with model: {model_name}")
            logger.info(f"  Embedding dimension: {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Failed to initialize vectorizer: {str(e)}")
            raise
    
    def vectorize(self, text: str) -> List[float]:
        """
        Convert text to vector embedding
        
        Args:
            text: Text to vectorize
        
        Returns:
            Vector embedding as list of floats
        """
        if not text or not isinstance(text, str):
            logger.warning("Empty or invalid text for vectorization")
            return [0.0] * self.embedding_dim
        
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error vectorizing text: {str(e)}")
            return [0.0] * self.embedding_dim
    
    def vectorize_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Vectorize multiple texts efficiently
        
        Args:
            texts: List of texts to vectorize
        
        Returns:
            List of vector embeddings
        """
        if not texts:
            return []
        
        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Error vectorizing batch: {str(e)}")
            return [[0.0] * self.embedding_dim for _ in texts]
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
        
        Returns:
            Similarity score (0-1)
        """
        if not vec1 or not vec2:
            return 0.0
        
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    def find_most_similar(
        self,
        query_vector: List[float],
        candidate_vectors: List[Tuple[str, List[float]]],
        top_k: int = 5,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Find most similar vectors from candidates
        
        Args:
            query_vector: Query vector
            candidate_vectors: List of (id, vector) tuples
            top_k: Number of top results to return
            threshold: Minimum similarity score
        
        Returns:
            List of {id, similarity, score} dicts sorted by similarity descending
        """
        if not candidate_vectors:
            return []
        
        similarities = []
        for candidate_id, candidate_vec in candidate_vectors:
            sim = self.cosine_similarity(query_vector, candidate_vec)
            if sim >= threshold:
                similarities.append({
                    "id": candidate_id,
                    "similarity": sim,
                    "score": round(sim, 4)
                })
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return similarities[:top_k]
