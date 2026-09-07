"""
Command-Line Interface for Chatbot
"""

import asyncio
import uuid
import logging
import sqlite3
from pathlib import Path
import sys
import io

# Fix Unicode encoding on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from .config import config
from .data.cache import SimpleCache
from .core.orchestrator import ChatbotOrchestrator
from .llm.openrouter import OpenRouterLLM, MockLLM
from .sync.auto_sync import DataSyncEngine

class ChatbotCLI:
    """Command-line interface for chatbot"""
    
    def __init__(self, auto_sync: bool = True):
        """Initialize CLI with optional auto-sync"""
        
        # Auto-sync latest data from archive
        if auto_sync:
            logger.info("Running auto-sync to load latest candidate data...")
            sync_engine = DataSyncEngine(
                db_path=config.DB_PATH,
                data_archive_dir=str(config.ARCHIVE_PATH)  # Action 227: DATA_ROOT/archive
            )
            sync_engine.sync()
        
        self.cache = SimpleCache(default_ttl=config.CACHE_TTL)
        self.session_id = str(uuid.uuid4())
        
        # Initialize database connection
        try:
            self.db_conn = sqlite3.connect(config.DB_PATH)
            self.db_conn.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {config.DB_PATH}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            self.db_conn = None
        
        # Initialize LLM with rate limiting from config
        if config.OPENROUTER_API_KEY:
            self.llm = OpenRouterLLM(
                api_key=config.OPENROUTER_API_KEY,
                model=config.LLM_MODEL,
                temperature=config.LLM_TEMPERATURE,
                max_tokens=config.LLM_MAX_TOKENS,
                timeout=config.LLM_TIMEOUT,
                max_requests_per_minute=config.LLM_MAX_REQUESTS_PER_MINUTE,
                retry_wait_seconds=config.LLM_RETRY_WAIT_SECONDS,
                max_retries=config.LLM_MAX_RETRIES
            )
            logger.info(f"Using OpenRouter LLM: {config.LLM_MODEL}")
            logger.info(f"Rate limit: {config.LLM_MAX_REQUESTS_PER_MINUTE} req/min, Timeout: {config.LLM_TIMEOUT}s, Max retries: {config.LLM_MAX_RETRIES}")
        else:
            self.llm = MockLLM()
            logger.warning("No OPENROUTER_API_KEY set - using mock LLM")
        
        # Initialize orchestrator with db_path for RAG
        self.orchestrator = ChatbotOrchestrator(
            db_session=self.db_conn,
            chroma_client=None,
            cache=self.cache,
            llm_client=self.llm,
            db_path=str(config.DB_PATH)
        )
        
        logger.info(f"Chatbot initialized with session: {self.session_id}")
    
    def print_banner(self):
        """Print welcome banner"""
        print("\n" + "="*80)
        print(">> CANDIDATE CHATBOT - INTERACTIVE MODE")
        print("="*80)
        print(f"Session ID: {self.session_id}")
        print("\nTry asking:")
        print("  * 'Tell me about John Doe'")
        print("  * 'Who has Docker?'")
        print("  * 'Show top 5 candidates'")
        print("  * 'Compare John and Jane'")
        print("  * 'Find candidates from Paris with Python'")
        print("\nType 'help' for more commands or 'exit' to quit.")
        print("="*80 + "\n")
    
    def print_help(self):
        """Print help message"""
        print("\n" + "-"*80)
        print("AVAILABLE COMMANDS")
        print("-"*80)
        print("Commands:")
        print("  help              Show this help message")
        print("  clear             Clear conversation history")
        print("  session           Show current session info")
        print("  exit              Exit the chatbot")
        print("\nQuery Examples:")
        print("  Profile:          'Tell me about John Doe'")
        print("  Search:           'Who has Docker and Python?'")
        print("  Comparison:       'Compare John and Jane'")
        print("  Ranking:          'Show top 10 candidates'")
        print("  Filter:           'Find candidates from Paris with 5+ years'")
        print("  Gap Analysis:     'What skills are missing?'")
        print("  Statistics:       'How many have Docker?'")
        print("-"*80 + "\n")
    
    async def chat_loop(self):
        """Main chat loop"""
        self.print_banner()
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() == "exit":
                    print("\nGoodbye! 👋")
                    break
                
                elif user_input.lower() == "help":
                    self.print_help()
                    continue
                
                elif user_input.lower() == "clear":
                    self.orchestrator.clear_session(self.session_id)
                    print("✓ Conversation history cleared\n")
                    continue
                
                elif user_input.lower() == "session":
                    info = self.orchestrator.get_session_info(self.session_id)
                    print(f"\nSession Info:")
                    print(f"  ID: {info['session_id']}")
                    print(f"  Created: {info['created_at']}")
                    print(f"  Turns: {info['turns']}")
                    print(f"  Last candidate: {info['last_candidate']}")
                    print(f"  Last intent: {info['last_intent']}")
                    if info['recent_candidates']:
                        print(f"  Recent candidates: {', '.join(info['recent_candidates'])}")
                    print()
                    continue
                
                # Process query
                print("\nBot: ", end="", flush=True)
                
                response = await self.orchestrator.chat(
                    query=user_input,
                    session_id=self.session_id
                )
                
                if response.get("success"):
                    print(response["response"])
                    
                    # Show metadata
                    intent = response.get("intent")
                    confidence = response.get("confidence", 0)
                    time_ms = response.get("query_time_ms", 0)
                    sources = response.get("sources", [])
                    
                    metadata = f"\n[Intent: {intent} ({confidence:.0%}), Time: {time_ms}ms"
                    if sources:
                        metadata += f", Sources: {', '.join(sources[:3])}"
                    metadata += "]\n"
                    
                    print(metadata)
                else:
                    print(f"Error: {response.get('error', 'Unknown error')}\n")
            
            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋")
                break
            
            except Exception as e:
                logger.error(f"Error in chat loop: {str(e)}")
                print(f"Error: {str(e)}\n")
    
    def run(self):
        """Run the chatbot"""
        try:
            asyncio.run(self.chat_loop())
        
        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")
            print(f"Fatal error: {str(e)}")
        
        finally:
            if self.db_conn:
                self.db_conn.close()
            logger.info("Chatbot session ended")


def main():
    """Entry point"""
    cli = ChatbotCLI()
    cli.run()


if __name__ == "__main__":
    main()
