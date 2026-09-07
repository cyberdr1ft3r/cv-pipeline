"""
Main Chatbot Orchestrator
Coordinates all chatbot components
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from .intent_detector import IntentDetector
from .entity_extractor import EntityExtractor
from .query_router import QueryRouter
from .response_generator import ResponseGenerator
from .context_manager import ContextManager
from .validators import ResponseValidator
from .conversation_coordinator import ConversationCoordinator
from .data_analytics import DataAnalytics
from .vectorizer import Vectorizer
from .semantic_search import SemanticSearch
from .rag_context import RAGContextManager

logger = logging.getLogger(__name__)

class ChatbotOrchestrator:
    """
    Main orchestrator that coordinates all chatbot components.
    
    Flow:
    1. Get conversation context
    2. Detect intent from query
    3. Extract entities
    4. Build and execute query
    5. Validate results
    6. Generate response
    7. Store context for next turn
    """
    
    def __init__(self, db_session, chroma_client=None, cache=None, llm_client=None, db_path: str = None):
        """Initialize orchestrator with all dependencies"""
        self.db = db_session
        self.chroma = chroma_client
        self.cache = cache
        self.llm = llm_client
        self.db_path = db_path
        
        # Initialize components
        self.intent_detector = IntentDetector(llm_client)
        self.entity_extractor = EntityExtractor(db_session)
        self.query_router = QueryRouter(db_session, chroma_client, cache)
        self.response_generator = ResponseGenerator(llm_client)
        self.context_manager = ContextManager(cache)
        self.validator = ResponseValidator(db_session)
        self.data_analytics = DataAnalytics(db_session)  # Full data visibility
        
        # Initialize conversation coordinator for human-like conversation
        self.conversation_coordinator = ConversationCoordinator(cache=cache)
        
        # Initialize RAG components (Retrieval-Augmented Generation)
        try:
            self.vectorizer = Vectorizer(model_name="all-MiniLM-L6-v2")
            self.semantic_search = SemanticSearch(db_path, self.vectorizer, cache)
            self.rag_context = RAGContextManager(self.semantic_search, self.vectorizer, cache)
            logger.info("RAG components initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize RAG components: {str(e)}")
            self.vectorizer = None
            self.semantic_search = None
            self.rag_context = None
        
        logger.info("Chatbot orchestrator initialized")
    
    async def chat(
        self,
        query: str,
        session_id: str,
        stream: bool = False
    ) -> Dict:
        """
        Main chat method - orchestrates all steps.
        
        Args:
            query: User's natural language query
            session_id: Conversation session ID
            stream: Whether to stream response (future feature)
        
        Returns:
            {
                "response": "...",
                "sources": [...],
                "entities_found": {...},
                "confidence": 0.95,
                "query_time_ms": 150,
                "intent": "profile",
                "success": True
            }
        """
        
        start_time = datetime.now()
        logger.info(f"[{session_id}] Processing query: {query[:50]}...")
        
        try:
            # Step 0: Preprocess query with ConversationCoordinator
            # (resolve pronouns and detect follow-ups)
            resolved_query, preprocessing_info = self.conversation_coordinator.preprocess_query(
                query=query,
                session_id=session_id
            )
            
            if preprocessing_info['had_pronouns']:
                logger.debug(f"Resolved pronouns: {preprocessing_info['resolved_pronouns']}")
            if preprocessing_info['followup_type']:
                logger.debug(f"Detected follow-up: {preprocessing_info['followup_type']} (confidence: {preprocessing_info['followup_confidence']:.2f})")
            
            # Step 1: Get conversation context
            context = self.context_manager.get_context(session_id)
            logger.debug(f"Retrieved context: {len(context['history'])} turns")
            
            # Step 2: Detect intent
            intent_result = self.intent_detector.detect(
                query=resolved_query,
                conversation_history=context['history']
            )
            intent = intent_result['type']
            confidence = intent_result['confidence']
            
            logger.info(f"Detected intent: {intent} (confidence: {confidence:.2f})")
            
            # Step 2b: Handle general conversation
            if intent == "conversation":
                logger.info("Entering conversation mode (general discussion)")
                response_text = self._generate_conversation_response(
                    query=query,
                    context=context,
                    preprocessing_info=preprocessing_info
                )
                
                # Store in context for next turn
                self.context_manager.add_turn(
                    session_id=session_id,
                    user_query=query,
                    bot_response=response_text,
                    intent=intent,
                    entities={}
                )
                
                # Record turn in conversation coordinator
                self.conversation_coordinator.record_turn(
                    session_id=session_id,
                    user_query=query,
                    bot_response=response_text,
                    intent=intent,
                    entities={},
                    results=[],
                    preprocessing_info=preprocessing_info
                )
                
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                return {
                    "response": response_text,
                    "sources": [],
                    "entities_found": {},
                    "confidence": confidence,
                    "query_time_ms": round(elapsed_ms, 1),
                    "intent": intent,
                    "success": True
                }
            
            if confidence < 0.4:
                # Unclear intent - ask for clarification
                logger.warning(f"Low confidence intent: {confidence}")
                return await self._handle_unclear_intent(query, session_id)
            
            # Step 3: Extract entities
            entities = self.entity_extractor.extract(
                query=resolved_query,
                intent=intent,
                context=self.context_manager.get_implicit_context(session_id)
            )
            logger.debug(f"Extracted entities: {entities}")
            
            # Step 4: Route and execute query
            query_results = self.query_router.route(
                intent=intent,
                entities=entities,
                context=context,
                original_query=resolved_query
            )
            
            logger.info(f"Query returned {len(query_results['data'])} results")
            
            # Handle no results with smart suggestions
            if not query_results['data']:
                logger.info(f"No results found for {intent} query")
                return self._handle_no_results(
                    intent=intent,
                    query=query,
                    entities=entities,
                    session_id=session_id,
                    start_time=start_time,
                    preprocessing_info=preprocessing_info
                )
            
            # Step 5: Validate results
            validation = self.validator.validate(
                results=query_results['data'],
                intent=intent,
                entities=entities
            )
            
            if not validation['is_valid']:
                logger.warning(f"Validation failed: {validation['reason']}")
                return await self._handle_invalid_results(
                    validation, intent, session_id
                )
            
            # Log any warnings
            if validation['warnings']:
                logger.warning(f"Validation warnings: {validation['warnings']}")
            
            # Step 6: Generate response
            response_result = self.response_generator.generate(
                intent=intent,
                query_results=query_results,
                entities=entities,
                context=context,
                stream=stream
            )
            
            # Step 7: Store in context for next turn
            self.context_manager.add_turn(
                session_id=session_id,
                user_query=query,
                bot_response=response_result['response'],
                intent=intent,
                entities=entities
            )
            
            # Step 7b: Record turn in conversation coordinator
            self.conversation_coordinator.record_turn(
                session_id=session_id,
                user_query=query,
                bot_response=response_result['response'],
                intent=intent,
                entities=entities,
                results=query_results['data'],
                preprocessing_info=preprocessing_info
            )
            
            # Prepare final response
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            final_response = {
                "response": response_result['response'],
                "sources": response_result.get('sources', []),
                "entities_found": entities,
                "confidence": confidence,
                "query_time_ms": round(elapsed_ms, 1),
                "intent": intent,
                "success": True
            }
            
            logger.info(f"✓ Response generated in {elapsed_ms:.0f}ms")
            return final_response
            
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}", exc_info=True)
            return {
                "response": f"I encountered an error: {str(e)}",
                "success": False,
                "error": str(e),
                "query_time_ms": round(
                    (datetime.now() - start_time).total_seconds() * 1000, 1
                )
            }
    
    def _generate_conversation_response(self, query: str, context: Dict, preprocessing_info: Dict) -> str:
        """
        Generate response for general conversation mode using LLM with RAG.
        
        RAG Workflow:
        1. Vectorize user prompt
        2. Search all DBs for similarity
        3. Collect relevant information
        4. Enrich LLM prompt with context
        5. Generate human-like response
        """
        
        # Check if this is a topic inquiry (asking about available topics/data)
        topic_response = self._generate_topic_response(query)
        if topic_response:
            return topic_response
        
        # Check for data-related queries that need immediate response
        data_response = self._handle_data_inquiry(query)
        if data_response:
            return data_response
        
        if not self.llm:
            return "I'd be happy to discuss! However, I need an LLM configured to have a free-form conversation."
        
        # Use RAG to enrich the prompt with context
        if self.rag_context:
            try:
                # Step 1: Retrieve context from databases (vectorization happens internally)
                # Search ALL tables with universal semantic search
                retrieved_context = self.rag_context.retrieve_context(
                    query=query,
                    limit_per_table=10,
                    similarity_threshold=0.25
                )
                
                # Step 2: Enrich the LLM prompt with retrieved context
                enriched_prompt = self.rag_context.enrich_llm_prompt(query, retrieved_context)
                
                logger.debug(f"RAG enriched prompt: {len(enriched_prompt)} chars")
                response = self.llm.generate(enriched_prompt)
            except Exception as e:
                logger.warning(f"RAG context enrichment failed, using standard prompt: {str(e)}")
                response = self._generate_conversation_response_standard(query, context)
        else:
            # Fallback to standard response if RAG not available
            response = self._generate_conversation_response_standard(query, context)
        
        # Check if response is an error message
        if response and response.startswith("[") and response.endswith("]"):
            logger.warning(f"LLM returned error: {response}")
            return self._generate_fallback_response(query)
        
        return response.strip() if response else self._generate_fallback_response(query)
    
    def _generate_conversation_response_standard(self, query: str, context: Dict) -> str:
        """
        Standard conversation response without RAG (fallback method)
        """
        # Build conversation history for context
        history_str = ""
        if context.get('history'):
            for turn in context['history'][-3:]:  # Last 3 turns for context
                history_str += f"User: {turn.get('query', '')}\nBot: {turn.get('response', '')}\n\n"
        
        # Get database stats for context-aware response
        stats = self.data_analytics.get_summary_stats()
        
        prompt = f"""You are a friendly, knowledgeable HR assistant having a natural conversation about candidate data.

Database Context:
- Total Candidates: {stats.get('total_candidates', 0)}
- Average Score: {stats.get('average_score', 0)}
- Unique Skills: {stats.get('total_skills', 0)}

Previous conversation:
{history_str if history_str else "(This is the start of conversation)"}

User's latest message: "{query}"

Your response should:
1. Be conversational and natural (like chatting with a colleague)
2. Show enthusiasm about the candidate data
3. Offer to help with specific actions (search, compare, analyze, list)
4. Ask clarifying questions if needed
5. Keep it brief and engaging (2-3 sentences)
6. Suggest next steps naturally
7. Be supportive of exploring the full database

Important: If the user asks about something unclear, offer specific examples.
For instance, if they ask "what can you do?", suggest: "search by skills", "compare candidates", "find by location", "list all candidates".

Response:"""
        
        try:
            response = self.llm.generate(prompt)
            logger.debug("Generated conversation response via LLM")
            return response.strip() if response else self._generate_fallback_response(query)
        except Exception as e:
            logger.error(f"Error generating conversation response: {str(e)}")
            return self._generate_fallback_response(query)
    
    def _generate_fallback_response(self, query: str) -> str:
        """
        Generate response without LLM when API fails.
        Uses database and predefined responses.
        """
        query_lower = query.lower()
        
        # Try data inquiry first
        data_response = self._handle_data_inquiry(query)
        if data_response:
            return data_response
        
        # Try conversational fallback
        fallback = self._get_conversational_fallback(query, "conversation")
        if fallback:
            return fallback
        
        # Generic fallback
        return (
            "I'm here to help you explore candidate data! "
            "Try asking me about specific candidates, skills we have, or get an overview of our database. "
            "What would you like to know?"
        )
    
    def _handle_data_inquiry(self, query: str) -> str:
        """
        Handle specific data inquiries that don't need LLM.
        Checks database directly for facts.
        """
        query_lower = query.lower()
        
        # "What skills do we have?" or similar
        if any(p in query_lower for p in ['what skills', 'which skills', 'all skills', 'list skills', 'available skills']):
            skills = self.data_analytics.get_skill_distribution()
            if skills:
                top_skills = dict(list(skills.items())[:15])
                formatted = self.data_analytics.get_skills_list_formatted(top_skills)
                return f"Here are the top skills we have in our database:\n\n{formatted}\n\nWould you like to search for candidates with any specific skill?"
        
        # "Where are candidates from?" or "What locations?"
        if any(p in query_lower for p in ['what locations', 'which locations', 'where are', 'candidate locations', 'all locations']):
            locations = self.data_analytics.get_all_locations()
            if locations:
                loc_text = ", ".join(locations)
                return f"Our candidates are from these locations:\n\n{loc_text}\n\nWould you like to search for candidates from any specific location?"
        
        # "How many candidates?"
        if any(p in query_lower for p in ['how many candidates', 'total candidates', 'candidate count', 'number of candidates']):
            count = self.data_analytics.get_candidate_count()
            return f"We currently have {count} candidates in our database. Would you like to explore them by skills, location, or see the top-ranked candidates?"
        
        return None
    
    
    def _generate_topic_response(self, query: str) -> str:
        """
        Generate educational response when user asks about available topics/data.
        
        Topics include: profiles, candidates, skills, experience, education, projects, etc.
        """
        query_lower = query.lower().strip()
        
        # Map topics to descriptions
        topic_descriptions = {
            'profiles': (
                "We have comprehensive candidate profiles that include their work experience, "
                "skills, education, certifications, and accomplishments. Each profile contains "
                "detailed information to help you evaluate candidates effectively. "
                "You can ask me about a specific person, or search by criteria like skills or location!"
            ),
            'candidates': (
                "Our database contains information about many talented candidates across various "
                "industries and experience levels. You can search for candidates by skills, location, "
                "experience level, or specific criteria. Want me to help you find someone specific?"
            ),
            'skills': (
                "We track the technical and professional skills of our candidates - things like "
                "programming languages (Python, Java, JavaScript), tools (Docker, Kubernetes), "
                "frameworks (React, Django), and soft skills. You can search for candidates with "
                "specific skills or ask me to analyze skill distribution across our candidate base."
            ),
            'experience': (
                "Our candidate data includes detailed work history and experience information. "
                "We track years of experience, previous roles, industries, and key achievements. "
                "This helps match candidates to your specific experience requirements."
            ),
            'education': (
                "We maintain education records for our candidates including degrees, universities, "
                "certifications, and professional qualifications. You can search for candidates with "
                "specific educational backgrounds or certifications."
            ),
            'projects': (
                "Candidates have documented their key projects and accomplishments. This includes "
                "project descriptions, technologies used, and impact. Great for evaluating practical "
                "experience and relevant work!"
            ),
            'data': (
                "Our candidate database is comprehensive and well-organized. We have profiles, skills, "
                "experience, education, projects, certifications, and more. What specific aspect of "
                "the data would you like to explore?"
            ),
        }
        
        # Check for single-word topic queries
        for topic, description in topic_descriptions.items():
            if query_lower == topic or query_lower == topic + 's':
                logger.debug(f"Generating topic-aware response for: {topic}")
                return description
        
        return None
    
    def _get_conversational_fallback(self, query: str, intent: str) -> str:
        """
        Handle broad queries that don't map to database searches.
        Examples: 'list all', 'show everyone', 'all candidates', etc.
        
        Full data visibility - NO LIMITATIONS
        """
        query_lower = query.lower()
        
        # Patterns for queries that need conversational handling
        list_all_patterns = [
            'list all', 'show all', 'all candidates', 'everyone', 'all names',
            'total candidates', 'how many', 'all profiles', 'entire list',
            'give me all', 'show me all', 'list candidates', 'see all', 'all of them'
        ]
        
        if any(pattern in query_lower for pattern in list_all_patterns):
            # Get ALL candidates from database - FULL VISIBILITY
            candidates = self.data_analytics.get_all_candidates()
            
            if not candidates:
                return "Currently, we don't have any candidates in the database. Would you like me to help you set up the system or load candidate data?"
            
            count = len(candidates)
            formatted_list = self.data_analytics.get_candidates_list_formatted(candidates)
            
            return (
                f"Here are all {count} candidates in our database:\n\n"
                f"{formatted_list}\n\n"
                f"You can ask me about any candidate, search by skills, filter by location, "
                f"or get more detailed information about anyone specific!"
            )
        
        # Check for capability queries
        capability_patterns = [
            'what can you', 'what do you', 'your capabilities', 'what are you able',
            'can you', 'do you support', 'what do we have', 'tell me what'
        ]
        
        if any(pattern in query_lower for pattern in capability_patterns):
            stats = self.data_analytics.get_summary_stats()
            
            return (
                f"Here's what I can help you with! 🎯\n\n"
                f"📊 **Database Overview:**\n"
                f"• Total candidates: {stats.get('total_candidates', 0)}\n"
                f"• Average score: {stats.get('average_score', 0)}\n"
                f"• Unique skills: {stats.get('total_skills', 0)}\n"
                f"• Locations: {stats.get('total_locations', 0)}\n\n"
                f"**What I can do:**\n"
                f"• Search by skills (e.g., 'Who has Python?')\n"
                f"• Find by location (e.g., 'Candidates from Paris')\n"
                f"• Search by experience (e.g., 'Senior developers')\n"
                f"• Compare candidates (e.g., 'Compare John and Jane')\n"
                f"• Show specific person (e.g., 'Tell me about Zakaria')\n"
                f"• Get rankings (e.g., 'Top 5 candidates')\n"
                f"• List all candidates (e.g., 'Show all candidates')\n"
                f"• Skill analytics (e.g., 'What skills do we have?')\n\n"
                f"What would you like to explore?"
            )
        
        # Check for stats/analytics queries
        if any(p in query_lower for p in ['stats', 'statistics', 'how many', 'total', 'overview', 'summary']):
            stats = self.data_analytics.get_summary_stats()
            skills = self.data_analytics.get_skill_distribution()
            
            return (
                f"📈 **Candidate Database Statistics:**\n\n"
                f"Total Candidates: {stats.get('total_candidates', 0)}\n"
                f"Average Score: {stats.get('average_score', 0)}\n"
                f"Unique Skills: {stats.get('total_skills', 0)}\n"
                f"Locations Represented: {stats.get('total_locations', 0)}\n\n"
                f"**Top Skills in Database:**\n"
                f"{self.data_analytics.get_skills_list_formatted(skills)}\n\n"
                f"Want to dive deeper into any skill or location?"
            )
        
        return None
    
    def _handle_no_results(self, intent: str, query: str, entities: Dict, session_id: str, 
                           start_time: datetime, preprocessing_info: Dict) -> Dict:
        """
        Smart handling when a query returns no results.
        Uses RAG to search ALL tables and provide comprehensive response with actual data.
        """
        
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Use RAG to search ALL tables for relevant information
        if self.rag_context:
            try:
                logger.info(f"No direct results found - using RAG to search ALL tables for: {query}")
                
                # Retrieve context from ALL database tables
                retrieved_context = self.rag_context.retrieve_context(
                    query=query,
                    limit_per_table=10,
                    similarity_threshold=0.20  # Lower threshold to find more matches
                )
                
                # Build LLM prompt with retrieved context
                enriched_prompt = self.rag_context.enrich_llm_prompt(query, retrieved_context)
                
                if enriched_prompt:
                    logger.info(f"RAG enriched prompt with {len(enriched_prompt)} chars")
                    response = self.llm.generate(enriched_prompt)
                    
                    if response and not response.startswith("["):
                        logger.info("Using RAG-enriched response")
                        self.context_manager.add_turn(
                            session_id=session_id,
                            user_query=query,
                            bot_response=response,
                            intent="search_with_rag",
                            entities=entities
                        )
                        return {
                            "response": response,
                            "sources": [],
                            "entities_found": entities,
                            "confidence": 0.85,
                            "query_time_ms": round(elapsed_ms, 1),
                            "intent": "search_with_rag",
                            "success": True
                        }
            except Exception as e:
                logger.warning(f"RAG enrichment in no_results handler failed: {str(e)}")
                # Continue to fallback approach
        
        # Check if this is a broad query that needs conversational handling
        conversational_response = self._get_conversational_fallback(query, intent)
        if conversational_response:
            logger.info(f"Using conversational fallback for broad query: {query}")
            self.context_manager.add_turn(
                session_id=session_id,
                user_query=query,
                bot_response=conversational_response,
                intent="conversation",
                entities={}
            )
            return {
                "response": conversational_response,
                "sources": [],
                "entities_found": entities,
                "confidence": 0.8,
                "query_time_ms": round(elapsed_ms, 1),
                "intent": "conversation",
                "success": True
            }
        
        # Use LLM to generate helpful suggestions
        if self.llm:
            prompt = f"""A user searched for: "{query}"
Intent: {intent}
But no results were found.

Generate a friendly, helpful response that:
1. Acknowledges their query
2. Explains why no results were found
3. Suggests alternative searches or topics they could explore (e.g., "Try searching for X instead", "You could also ask about...")
4. Keeps it conversational and helpful (2-3 sentences)

Response:"""
            
            try:
                response = self.llm.generate(prompt)
                
                # Check if LLM returned error
                if response and response.startswith("[") and response.endswith("]"):
                    logger.warning(f"LLM error for suggestions: {response}")
                    suggestion = self._generate_default_suggestions(intent)
                else:
                    suggestion = response.strip()
                    logger.debug(f"Generated smart no-results response")
            except Exception as e:
                logger.error(f"Error generating suggestions: {str(e)}")
                suggestion = self._generate_default_suggestions(intent)
        else:
            suggestion = self._generate_default_suggestions(intent)
        
        # Store in context
        self.context_manager.add_turn(
            session_id=session_id,
            user_query=query,
            bot_response=suggestion,
            intent=intent,
            entities=entities
        )
        
        # Record in conversation coordinator
        self.conversation_coordinator.record_turn(
            session_id=session_id,
            user_query=query,
            bot_response=suggestion,
            intent=intent,
            entities=entities,
            results=[],
            preprocessing_info=preprocessing_info
        )
        
        return {
            "response": suggestion,
            "sources": [],
            "entities_found": entities,
            "confidence": 0.7,
            "query_time_ms": round(elapsed_ms, 1),
            "intent": intent,
            "success": True
        }
    
    def _generate_default_suggestions(self, intent: str) -> str:
        """Generate default suggestions based on intent type"""
        
        suggestions = {
            "profile": "I couldn't find that candidate. Would you like me to show you all candidates, or search by a specific skill or location?",
            "search": "I didn't find candidates matching those criteria. Try searching for a specific skill like 'Python', 'Docker', or 'AWS'.",
            "ranking": "Would you like to see the top candidates by overall match score, or narrow down by specific skills?",
            "comparison": "I couldn't find both candidates to compare. Try asking about specific people or search by skills instead.",
            "gap_analysis": "Let me help you find candidates with specific skills or gaps. What skills are you interested in learning about?",
            "filter": "No candidates matched those filters. Try adjusting your search criteria - maybe search by location or a single skill?",
            "aggregation": "Let me know what specific statistics you'd like - I can help with skill breakdowns, location distribution, or experience levels."
        }
        
        return suggestions.get(intent, "I didn't find what you were looking for. Can you provide more details about what you're searching for?")
    
    
    async def _handle_unclear_intent(self, query: str, session_id: str) -> Dict:
        """Handle queries with unclear intent"""
        
        logger.warning(f"Unclear intent for query: {query}")
        
        clarification_options = [
            "Tell me about a specific candidate (e.g., 'Tell me about John Doe')",
            "Search by skills (e.g., 'Who has Docker?')",
            "Compare candidates (e.g., 'Compare John and Jane')",
            "Show rankings (e.g., 'Show top 5')",
            "Filter by criteria (e.g., 'Find candidates from Paris with Python')"
        ]
        
        response_text = ("I'm not sure what you're asking. Could you try one of these:\n" +
                        "\n".join(f"• {opt}" for opt in clarification_options))
        
        return {
            "response": response_text,
            "success": True,
            "intent": "clarification_needed",
            "confidence": 0.3
        }
    
    async def _handle_invalid_results(self, validation: Dict, intent: str, session_id: str) -> Dict:
        """Handle cases where validation fails"""
        
        logger.error(f"Invalid results for intent {intent}: {validation['reason']}")
        
        return {
            "response": ("The data doesn't seem right. " +
                        f"Reason: {validation['reason']}"),
            "success": False,
            "validation_error": validation['reason'],
            "intent": intent
        }
    
    def get_session_info(self, session_id: str) -> Dict:
        """Get information about a session"""
        context = self.context_manager.get_context(session_id)
        
        return {
            "session_id": session_id,
            "created_at": context['created_at'],
            "turns": len(context['history']),
            "last_candidate": context['last_candidate'],
            "last_intent": context['last_intent'],
            "recent_candidates": context['recent_candidates']
        }
    
    def clear_session(self, session_id: str):
        """Clear session context"""
        self.context_manager.clear_context(session_id)
        logger.info(f"Cleared session: {session_id}")
