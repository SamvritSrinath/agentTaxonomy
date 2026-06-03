from app import admin_report, user_summary


def test_user_summary_returns_existing_user_summary():
    assert user_summary(1) == {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "active": True,
        "order_count": 2,
        "total_spent": 155.5,
    }


def test_user_summary_returns_404_for_missing_user():
    assert user_summary(999) == ({"error": "User not found"}, 404)


def test_admin_report_returns_report():
    assert admin_report() == {
        "total_users": 3,
        "active_users": 2,
        "admin_users": 1,
        "total_orders": 3,
        "total_revenue": 235.5,
    }
