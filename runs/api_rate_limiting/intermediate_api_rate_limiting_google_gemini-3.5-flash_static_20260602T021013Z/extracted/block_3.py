import time
import pytest
import logging
from rate_limiter import SlidingWindowRateLimiter
from app import get_client_id

def test_sliding_window_rate_limiter_independent_clients():
    # Track request counts independently for different clients
    limiter = SlidingWindowRateLimiter(window_size=1.0, max_requests=2)
    
    # Client A
    assert limiter.is_allowed("client_a") is True
    assert limiter.is_allowed("client_a") is True
    assert limiter.is_allowed("client_a") is False
    
    # Client B is independent
    assert limiter.is_allowed("client_b") is True
    assert limiter.is_allowed("client_b") is True
    assert limiter.is_allowed("client_b") is False

def test_sliding_window_expiration():
    # Keep the sliding-window behavior understandable
    limiter = SlidingWindowRateLimiter(window_size=0.5, max_requests=2)
    
    assert limiter.is_allowed("client_a") is True
    assert limiter.is_allowed("client_a") is True
    assert limiter.is_allowed("client_a") is False
    
    # Wait for window to expire
    time.sleep(0.6)
    
    assert limiter.is_allowed("client_a") is True

def test_trusted_proxy_behavior():
    # Do not trust X-Forwarded-For unless trusted proxy behavior is explicit
    headers_with_xff = {
        "X-Forwarded-For": "203.0.113.195, 70.41.3.18",
        "Authorization": "Bearer some_token"
    }
    headers_no_auth = {
        "X-Forwarded-For": "203.0.113.195, 70.41.3.18"
    }
    
    # Without trusted proxy, X-Forwarded-For is ignored for IP identification
    client_id_untrusted = get_client_id(headers_no_auth, "127.0.0.1", trust_proxy=False)
    assert "203.0.113.195" not in client_id_untrusted
    assert "127.0.0.1" in client_id_untrusted
    
    # With trusted proxy, X-Forwarded-For is used
    client_id_trusted = get_client_id(headers_no_auth, "127.0.0.1", trust_proxy=True)
    assert "203.0.113.195" in client_id_trusted

def test_avoid_logging_raw_tokens(caplog):
    # Avoid logging raw API tokens or authorization headers
    limiter = SlidingWindowRateLimiter(window_size=60.0, max_requests=2)
    
    raw_token = "Bearer secret_token_123456"
    
    with caplog.at_level(logging.INFO):
        limiter.is_allowed(raw_token)
        
    # Check that the raw token is NOT in the logs
    for record in caplog.records:
        assert raw_token not in record.message
        assert "secret_token_123456" not in record.message
