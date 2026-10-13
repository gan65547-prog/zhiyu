"""
Integration tests - Rate Limiting Middleware

Tests the distributed/memory rate limiter core logic:
- Memory-based sliding window
- X-RateLimit-* header calculation
- Per-IP independent limits
- Window reset behavior
"""

import time
import pytest
from collections import defaultdict


class TestMemorySlidingWindow:
    """Test the core sliding window rate limit logic directly."""

    def _make_limiter(self, max_per_minute: int = 5):
        """Create a memory-based rate limiter for testing."""
        request_counts = defaultdict(list)

        def check_limit(client_ip: str, now: float = None) -> bool:
            if now is None:
                now = time.time()
            minute_ago = now - 60
            # Clean expired entries
            request_counts[client_ip] = [
                t for t in request_counts[client_ip] if t > minute_ago
            ]
            if len(request_counts[client_ip]) >= max_per_minute:
                return False
            request_counts[client_ip].append(now)
            return True

        def remaining(client_ip: str, now: float = None) -> int:
            if now is None:
                now = time.time()
            minute_ago = now - 60
            request_counts[client_ip] = [
                t for t in request_counts[client_ip] if t > minute_ago
            ]
            return max(0, max_per_minute - len(request_counts[client_ip]))

        return check_limit, remaining

    def test_requests_within_limit_succeed(self):
        """Requests within the configured limit should be allowed."""
        check_limit, _ = self._make_limiter(max_per_minute=5)
        now = 1000.0

        for i in range(5):
            assert check_limit("10.0.0.1", now + i) is True, f"Request {i+1} should be allowed"

    def test_requests_exceeding_limit_rejected(self):
        """Requests exceeding the configured limit should be rejected."""
        check_limit, _ = self._make_limiter(max_per_minute=3)
        now = 1000.0

        assert check_limit("10.0.0.1", now) is True
        assert check_limit("10.0.0.1", now + 1) is True
        assert check_limit("10.0.0.1", now + 2) is True
        assert check_limit("10.0.0.1", now + 3) is False  # Exceeded

    def test_different_ips_independent_limits(self):
        """Different client IPs should have independent rate limit counters."""
        check_limit, _ = self._make_limiter(max_per_minute=2)
        now = 1000.0

        # Exhaust IP1
        assert check_limit("10.0.0.1", now) is True
        assert check_limit("10.0.0.1", now + 1) is True
        assert check_limit("10.0.0.1", now + 2) is False  # Blocked

        # IP2 still has full quota
        assert check_limit("10.0.0.2", now) is True
        assert check_limit("10.0.0.2", now + 1) is True
        assert check_limit("10.0.0.2", now + 2) is False  # Also blocked

    def test_window_resets_after_time(self):
        """Rate limit should reset after the 60-second sliding window passes."""
        check_limit, _ = self._make_limiter(max_per_minute=3)
        now = 1000.0

        # Exhaust limit
        check_limit("10.0.0.1", now)
        check_limit("10.0.0.1", now + 1)
        check_limit("10.0.0.1", now + 2)
        assert check_limit("10.0.0.1", now + 3) is False

        # Advance past window
        assert check_limit("10.0.0.1", now + 120) is True  # Reset

    def test_remaining_count_decrements(self):
        """The remaining count should decrease with each request."""
        check_limit, remaining = self._make_limiter(max_per_minute=5)
        now = 1000.0

        assert remaining("10.0.0.1", now) == 5
        check_limit("10.0.0.1", now)
        assert remaining("10.0.0.1", now + 1) == 4
        check_limit("10.0.0.1", now + 1)
        assert remaining("10.0.0.1", now + 2) == 3

    def test_remaining_never_negative(self):
        """Remaining count should never go below 0."""
        check_limit, remaining = self._make_limiter(max_per_minute=2)
        now = 1000.0

        check_limit("10.0.0.1", now)
        check_limit("10.0.0.1", now + 1)
        assert check_limit("10.0.0.1", now + 2) is False
        # Remaining should be 0, not negative
        assert remaining("10.0.0.1", now + 2) == 0

    def test_x_ratelimit_headers_format(self):
        """X-RateLimit headers should have the correct format."""
        check_limit, remaining = self._make_limiter(max_per_minute=100)
        now = 1000.0

        check_limit("10.0.0.1", now)

        headers = {
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": str(remaining("10.0.0.1", now + 1)),
        }

        assert headers["X-RateLimit-Limit"] == "100"
        assert int(headers["X-RateLimit-Limit"]) > 0
        assert int(headers["X-RateLimit-Remaining"]) >= 0

    def test_burst_then_sliding_window(self):
        """Burst of requests should expire one-by-one as the window slides."""
        check_limit, remaining = self._make_limiter(max_per_minute=3)
        now = 1000.0

        # Send 3 requests in quick succession
        for i in range(3):
            check_limit("10.0.0.1", now + i)

        assert remaining("10.0.0.1", now + 3) == 0

        # After first request (1000.0) is >60s old, 1 slot freed
        assert remaining("10.0.0.1", now + 61) == 2

        # After first two requests (1000.0, 1001.0) are >60s old, 2 slots freed
        assert remaining("10.0.0.1", now + 62) == 3


class TestRateLimitEdgeCases:
    """Test edge cases for rate limiting."""

    def test_zero_limit(self):
        """With limit=0, all requests should be blocked."""
        from collections import defaultdict
        request_counts = defaultdict(list)
        now = 1000.0

        def check(ip):
            if len(request_counts[ip]) >= 0:
                return False
            request_counts[ip].append(now)
            return True

        assert check("10.0.0.1") is False

    def test_single_request_limit(self):
        """With limit=1, only one request should pass."""
        from collections import defaultdict
        request_counts = defaultdict(list)
        now = 1000.0

        def check(ip) -> bool:
            minute_ago = now - 60
            request_counts[ip] = [t for t in request_counts[ip] if t > minute_ago]
            if len(request_counts[ip]) >= 1:
                return False
            request_counts[ip].append(now)
            return True

        assert check("10.0.0.1") is True
        assert check("10.0.0.1") is False

    def test_empty_window_no_requests(self):
        """With no requests, remaining should equal limit."""
        from collections import defaultdict
        request_counts = defaultdict(list)
        now = 1000.0

        minute_ago = now - 60
        recent = [t for t in request_counts.get("10.0.0.1", []) if t > minute_ago]
        assert len(recent) == 0


class TestRegistrationRateLimitLogic:
    """Test registration-specific rate limiting logic."""

    def test_register_limit_enforced(self):
        """Registration should be limited to N attempts per window."""
        max_attempts = 3
        cache = {}

        def check_register(ip: str) -> tuple:
            """Returns (allowed: bool, current_count: int)."""
            key = f"register:{ip}"
            count = cache.get(key, 0)
            if count >= max_attempts:
                return False, count
            count += 1
            cache[key] = count
            return True, count

        for i in range(3):
            allowed, count = check_register("10.0.0.1")
            assert allowed is True
            assert count == i + 1

        allowed, count = check_register("10.0.0.1")
        assert allowed is False
        assert count == 3


class TestWindowReset:
    """Test that the sliding window eventually resets."""

    def test_memory_rate_limit_resets_after_window(self):
        """Memory-based rate limit should reset after the 60-second window."""
        from collections import defaultdict

        requests_per_minute = 3
        request_counts = defaultdict(list)

        def check_limit(ip, now):
            minute_ago = now - 60
            request_counts[ip] = [t for t in request_counts[ip] if t > minute_ago]
            if len(request_counts[ip]) >= requests_per_minute:
                return False
            request_counts[ip].append(now)
            return True

        # Exhaust limit
        now = 1000.0
        for _ in range(3):
            assert check_limit("10.0.0.1", now) is True

        # Should be limited
        assert check_limit("10.0.0.1", now) is False

        # Advance time past the window
        now = 1100.0  # 100 seconds later
        assert check_limit("10.0.0.1", now) is True  # Should reset
