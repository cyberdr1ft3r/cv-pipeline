import time
from typing import Dict, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class ClientIdentifier:
    ip: str
    user_agent: str = ""
    api_key: str = ""

    def __hash__(self):
        return hash((self.ip, self.user_agent, self.api_key))

class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self, requests_per_minute: int = 5, requests_per_hour: int = None, requests_per_day: int = None):
        self.requests_per_minute = requests_per_minute
        # requests_per_hour and requests_per_day are accepted but not used
        self.requests: Dict[ClientIdentifier, list] = defaultdict(list)

    def is_allowed(self, client: ClientIdentifier) -> bool:
        """Check if client is within rate limits"""
        now = time.time()
        client_requests = self.requests[client]

        # Remove requests older than 1 minute
        client_requests[:] = [req_time for req_time in client_requests if now - req_time < 60]

        if len(client_requests) >= self.requests_per_minute:
            return False

        client_requests.append(now)
        return True

    def get_remaining_requests(self, client: ClientIdentifier) -> int:
        """Get remaining requests for client"""
        now = time.time()
        client_requests = self.requests[client]
        client_requests[:] = [req_time for req_time in client_requests if now - req_time < 60]
        return max(0, self.requests_per_minute - len(client_requests))

# Global rate limiter instance
rate_limiter = RateLimiter()