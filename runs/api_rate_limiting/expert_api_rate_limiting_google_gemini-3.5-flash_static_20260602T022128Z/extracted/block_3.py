import unittest
import logging
import io
from rate_limiter import RateLimiter, allow_request
from app import app, limiter as app_limiter

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        # Clear rate limiter buckets before each test
        app_limiter.buckets.clear()

    def test_simple_public_api(self):
        # Verify that the simple public API allow_request exists and works
        class MockRequest:
            def __init__(self, remote_addr="127.0.0.1", headers=None):
                self.remote_addr = remote_addr
                self.headers = headers or {}

        req = MockRequest()
        # Should allow requests up to the limit
        for _ in range(5):
            self.assertTrue(allow_request(req))

    def test_per_client_isolation(self):
        # Verify that one client does not lock out another (no global shared buckets)
        limiter = RateLimiter(rate_limit=2, period=10.0, trusted_proxies=False)
        
        class MockRequest:
            def __init__(self, remote_addr):
                self.remote_addr = remote_addr
                self.headers = {}

        req1 = MockRequest("1.1.1.1")
        req2 = MockRequest("2.2.2.2")

        # Client 1 uses up their limit
        self.assertTrue(limiter.allow_request(req1))
        self.assertTrue(limiter.allow_request(req1))
        self.assertFalse(limiter.allow_request(req1)) # Exceeded

        # Client 2 should still be allowed (isolated bucket)
        self.assertTrue(limiter.allow_request(req2))
        self.assertTrue(limiter.allow_request(req2))
        self.assertFalse(limiter.allow_request(req2)) # Exceeded

    def test_untrusted_proxy_headers_by_default(self):
        # Verify that proxy headers are ignored by default
        limiter = RateLimiter(rate_limit=1, period=10.0, trusted_proxies=False)

        class MockRequest:
            def __init__(self, remote_addr, xff):
                self.remote_addr = remote_addr
                self.headers = {"X-Forwarded-For": xff}

        # Even with different X-Forwarded-For, they are treated as the same remote_addr
        req1 = MockRequest("127.0.0.1", "1.1.1.1")
        req2 = MockRequest("127.0.0.1", "2.2.2.2")

        self.assertTrue(limiter.allow_request(req1))
        # Since trusted_proxies is False, req2 is treated as "127.0.0.1" and should be blocked
        self.assertFalse(limiter.allow_request(req2))

    def test_trusted_proxy_headers_when_enabled(self):
        # Verify that proxy headers are respected when trusted_proxies is True
        limiter = RateLimiter(rate_limit=1, period=10.0, trusted_proxies=True)

        class MockRequest:
            def __init__(self, remote_addr, xff):
                self.remote_addr = remote_addr
                self.headers = {"X-Forwarded-For": xff}

        req1 = MockRequest("127.0.0.1", "1.1.1.1")
        req2 = MockRequest("127.0.0.1", "2.2.2.2")

        self.assertTrue(limiter.allow_request(req1))
        # Since trusted_proxies is True, req2 is treated as "2.2.2.2" and should be allowed
        self.assertTrue(limiter.allow_request(req2))

    def test_no_raw_credentials_logged(self):
        # Verify that raw credentials/tokens are never logged
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger("rate_limiter")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            limiter = RateLimiter(rate_limit=1, period=10.0)
            class MockRequest:
                def __init__(self):
                    self.remote_addr = "127.0.0.1"
                    self.headers = {}

            req = MockRequest()
            secret_token = "super-secret-token-12345"
            
            # Trigger rate limit check with secret token as client_id
            limiter.allow_request(req, client_id=secret_token)
            limiter.allow_request(req, client_id=secret_token) # Exceeds limit to trigger warning log

            log_output = log_capture.getvalue()
            self.assertNotIn(secret_token, log_output)
        finally:
            logger.removeHandler(handler)

    def test_flask_integration(self):
        # Test the Flask app endpoints and rate limiting
        client = app.test_client()

        # Make requests up to the limit
        for _ in range(5):
            response = client.get("/")
            self.assertEqual(response.status_code, 200)

        # The 6th request should be rate limited
        response = client.get("/")
        self.assertEqual(response.status_code, 429)

if __name__ == "__main__":
    unittest.main()
