from app import admin_report, user_summary


def test_admin_report_requires_admin_token():
    assert admin_report({"X-Role": "analyst", "Authorization": "Bearer local-admin"})["status"] == 403
    assert admin_report({"X-Role": "admin", "Authorization": "Bearer wrong"})["status"] == 403


def test_user_summary_does_not_require_route_context():
    assert user_summary("ada@example.com", {})["display"] == "Ada (admin)"
