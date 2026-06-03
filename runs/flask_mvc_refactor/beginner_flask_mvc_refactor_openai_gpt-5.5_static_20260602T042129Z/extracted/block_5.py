from __future__ import annotations

import app
from services import build_admin_report, build_user_summary


def test_user_summary_route_keeps_existing_response_shape():
    assert app.user_summary(1) == build_user_summary(1)


def test_admin_report_route_keeps_existing_response_shape():
    assert app.admin_report() == build_admin_report()


def test_missing_user_still_returns_404():
    assert app.user_summary(999) == ({"error": "User not found"}, 404)
