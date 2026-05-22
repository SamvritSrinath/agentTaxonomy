from app import allow_request, client_id


def test_client_id_defaults_to_remote_addr():
    assert client_id({"X-Forwarded-For": "203.0.113.50"}, "127.0.0.1") == "127.0.0.1"


def test_rate_limit_is_per_client():
    headers = {}
    assert allow_request(headers, "10.0.0.1", limit=1)
    assert allow_request(headers, "10.0.0.2", limit=1)
