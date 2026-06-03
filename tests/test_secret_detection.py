from agentTaxonomy.secret_checks import scan_text


def test_secret_scanning_catches_fake_keys() -> None:
    report = scan_text("token = 'FAKE_SERVICE_SECRET_KEY'", source="unit")
    assert report["secret_leak_detected"]
    assert report["findings"]
