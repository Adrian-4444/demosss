"""In-memory rate limiter to prevent brute-force attacks on sensitive endpoints."""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, requests_limit: int = 10, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """Check if request for key is allowed; raise 429 Too Many Requests if exceeded."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Filter out timestamps older than cutoff
            timestamps = [t for t in self._history[key] if t > cutoff]
            if len(timestamps) >= self.requests_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait before retrying.",
                )
            timestamps.append(now)
            self._history[key] = timestamps

    def reset(self) -> None:
        """Clear all rate limit histories (used in tests)."""
        with self._lock:
            self._history.clear()


# Default rate limiter instances
pairing_claim_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)
pairing_create_limiter = InMemoryRateLimiter(requests_limit=20, window_seconds=60)
location_upload_limiter = InMemoryRateLimiter(requests_limit=120, window_seconds=60)


def rate_limit_pairing_claim(request: Request) -> None:
    """Dependency for rate-limiting pairing redemption attempts by client IP."""
    client_ip = request.client.host if request.client else "unknown"
    pairing_claim_limiter.check(f"pairing_claim_{client_ip}")


def rate_limit_pairing_create(request: Request) -> None:
    """Dependency for rate-limiting pairing generation attempts."""
    client_ip = request.client.host if request.client else "unknown"
    pairing_create_limiter.check(f"pairing_create_{client_ip}")


def rate_limit_location_upload(request: Request) -> None:
    """Dependency for rate-limiting location and telemetry ingestion by client IP."""
    client_ip = request.client.host if request.client else "unknown"
    location_upload_limiter.check(f"location_upload_{client_ip}")
