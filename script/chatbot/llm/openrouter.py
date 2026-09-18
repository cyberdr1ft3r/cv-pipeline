"""
OpenRouter LLM Integration
Handles all LLM calls via OpenRouter API
"""

from openai import OpenAI
from openai import APIStatusError, APIError
import httpx
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OpenRouterLLM:
    """Interface to OpenRouter LLM provider"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 30,
        max_requests_per_minute: int = 5,
        retry_wait_seconds: int = 5,
        max_retries: int = 5
    ):
        """
        Initialize OpenRouter LLM client with rate limiting
        
        Args:
            api_key: OpenRouter API key
            model: Model to use
            temperature: Temperature for generation (0-1)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            max_requests_per_minute: Rate limit for requests
            retry_wait_seconds: Seconds to wait before retry
            max_retries: Maximum retry attempts
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.base_url = "https://openrouter.ai/api/v1"
        self.max_requests_per_minute = max_requests_per_minute
        self.retry_wait_seconds = retry_wait_seconds
        self.max_retries = max_retries
        
        # Use the platform trust store and normal TLS certificate validation.
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=api_key,
        )
        
        # Rate limiting
        self.request_times = []  # Track last requests
        self.min_interval = 60.0 / max_requests_per_minute  # Min seconds between requests
        
        if not api_key:
            logger.warning("No OpenRouter API key provided")
    
    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit"""
        now = time.time()
        
        # Remove old timestamps outside the 1-minute window
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # Check if we've hit the rate limit
        if len(self.request_times) >= self.max_requests_per_minute:
            # Wait until the oldest request is outside the window
            wait_time = 60 - (now - self.request_times[0]) + 0.1
            if wait_time > 0:
                logger.info(f"Rate limit reached. Waiting {wait_time:.1f}s before next request...")
                time.sleep(wait_time)
        
        self.request_times.append(time.time())
    
    def _exponential_backoff(self, attempt: int) -> int:
        """Calculate exponential backoff time"""
        return min(self.retry_wait_seconds * (2 ** attempt), 60)
    
    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using OpenRouter LLM with rate limiting and retries
        
        Args:
            prompt: Input prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens
        
        Returns:
            Generated text
        """
        
        if not self.api_key:
            logger.warning("No API key available, returning empty response")
            return ""
        
        temperature = temperature or self.temperature
        max_tokens = max_tokens or self.max_tokens
        
        # Retry logic with exponential backoff (max 2 retries for rate limits)
        max_attempts = min(self.max_retries, 2)  # Limit retries for faster fallback
        
        for attempt in range(max_attempts):
            try:
                # Apply rate limiting
                self._wait_for_rate_limit()
                
                logger.debug(f"Calling OpenRouter with model: {self.model}")
                
                # Use OpenAI client with httpx
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://candidate-chatbot.local",
                        "X-Title": "Candidate Chatbot",
                    },
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.timeout
                )
                
                # Validate response structure
                if not completion or not hasattr(completion, 'choices') or not completion.choices:
                    logger.error(f"Invalid response structure: completion={completion}")
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        logger.warning(f"Invalid response (attempt {attempt + 1}/{max_attempts}). Retrying in {backoff}s...")
                        time.sleep(backoff)
                        continue
                    return "[Invalid LLM response structure]"
                
                text = completion.choices[0].message.content
                if not text:
                    logger.error("Empty content in response")
                    return "[Empty LLM response]"
                
                logger.debug(f"Generated {len(text)} chars")
                return text
                
            except APIStatusError as e:
                # Handle OpenAI API errors (402, 401, 429, etc.)
                status_code = e.status_code
                
                if status_code == 429:  # Rate limit
                    if attempt >= 1:  # Only retry once
                        logger.warning(f"Rate limit persists after retry. Failing over to database responses.")
                        return "[LLM rate limited - falling back to database responses]"
                    backoff = self._exponential_backoff(attempt)
                    logger.warning(f"Rate limited (attempt {attempt + 1}/{max_attempts}). Waiting {backoff}s...")
                    time.sleep(backoff)
                    continue
                
                elif status_code == 402:  # Payment required / quota exceeded
                    logger.warning(f"OpenRouter 402: Payment/quota exceeded. API key limit reached.")
                    return "[LLM quota exceeded - falling back to database responses]"
                
                elif status_code == 401:  # Unauthorized
                    logger.warning(f"OpenRouter 401: Unauthorized. Check API key.")
                    return "[LLM authentication failed - falling back to database responses]"
                
                elif status_code >= 500 and attempt < max_attempts - 1:  # Server error
                    backoff = self._exponential_backoff(attempt)
                    logger.info(f"Server error {status_code}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue
                
                else:
                    logger.debug(f"OpenRouter error {status_code}")
                    return f"[OpenRouter Error: {status_code}]"
            
            except httpx.HTTPStatusError as e:
                # Fallback for direct httpx errors
                status_code = e.response.status_code
                logger.debug(f"HTTP error {status_code}")
                return f"[HTTP Error: {status_code}]"
            
            except APIError as e:
                # Catch any other OpenAI API errors
                logger.debug(f"OpenAI API error: {type(e).__name__}")
                return "[LLM error - falling back to database responses]"
            
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                backoff = self._exponential_backoff(attempt)
                if attempt < max_attempts - 1:
                    logger.warning(f"Network error (attempt {attempt + 1}/{max_attempts}). Retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue
                else:
                    logger.error(f"Network error (max retries exceeded): {type(e).__name__}")
                    return "[Network error - max retries exceeded]"
            
            except Exception as e:
                logger.error(f"Error calling OpenRouter: {str(e)}", exc_info=True)
                return f"[Error: {str(e)}]"
        
        return "[Failed after max retries]"
    
    def generate_stream(self, prompt: str):
        """
        Generate text with streaming (yields chunks)
        
        Args:
            prompt: Input prompt
        
        Yields:
            Text chunks
        """
        
        if not self.api_key:
            logger.warning("No API key available")
            return
        
        try:
            self._wait_for_rate_limit()
            
            logger.debug(f"Starting stream with model: {self.model}")
            
            with self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            ) as stream:
                for text in stream.text_stream:
                    yield text
        
        except Exception as e:
            logger.error(f"Error in stream: {str(e)}")
            yield f"[Error: {str(e)}]"
    
    def get_models(self) -> list:
        """Get list of available models"""
        
        try:
            models = self.client.models.list()
            return [model.id for model in models.data] if hasattr(models, 'data') else []
        
        except Exception as e:
            logger.error(f"Error getting models: {str(e)}")
            return []


class MockLLM:
    """Mock LLM for testing without API key"""
    
    def __init__(self):
        logger.warning("Using mock LLM (no real API calls)")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Return mock response"""
        return "[Mock LLM Response - Set OPENROUTER_API_KEY to use real LLM]"
    
    def generate_stream(self, prompt: str):
        """Mock streaming"""
        yield "[Mock response]"
