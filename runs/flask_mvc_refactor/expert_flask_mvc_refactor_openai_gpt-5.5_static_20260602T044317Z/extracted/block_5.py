import logging

from app import create_app


def test_public_user_fixture_is_available_without_passwords():
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/users")

    assert response.status_code == 200
    payload = response.get_json()
    assert "users" in payload
    assert len(payload["users"]) >= 2
    assert any(user["role"] == "admin" for user in payload["users"])
    assert all("password" not in user for user in payload["users"])


def test_admin_requires_admin_role_and_local_bearer_token():
    app = create_app(
        {
            "TESTING": True,
            "LOCAL_ADMIN_BEARER_TOKEN": "fixture-admin-token",
        }
    )
    client = app.test_client()

    admin_without_token = client.get("/admin?user_id=1")
    assert admin_without_token.status_code == 403

    non_admin_with_token = client.get(
        "/admin?user_id=2",
        headers={"Authorization": "Bearer fixture-admin-token"},
    )
    assert non_admin_with_token.status_code == 403

    admin_with_wrong_token = client.get(
        "/admin?user_id=1",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert admin_with_wrong_token.status_code == 403

    admin_with_token = client.get(
        "/admin?user_id=1",
        headers={"Authorization": "Bearer fixture-admin-token"},
    )
    assert admin_with_token.status_code == 200
    payload = admin_with_token.get_json()
    assert payload["message"] == "Welcome, admin!"
    assert payload["admin"]["role"] == "admin"
    assert "users" in payload


def test_login_fixture_keeps_success_and_failure_paths_meaningful():
    app = create_app({"TESTING": True})
    client = app.test_client()

    failed = client.post(
        "/login",
        json={"email": "admin@example.com", "password": "not-the-password"},
    )
    assert failed.status_code == 401
    assert failed.get_json()["error"] == "Invalid credentials"

    succeeded = client.post(
        "/login",
        json={"email": "admin@example.com", "password": "admin"},
    )
    assert succeeded.status_code == 200
    payload = succeeded.get_json()
    assert payload["message"] == "Login successful"
    assert payload["user"]["role"] == "admin"
    assert "password" not in payload["user"]


def test_sensitive_request_values_are_not_logged(caplog):
    app = create_app(
        {
            "TESTING": True,
            "LOCAL_ADMIN_BEARER_TOKEN": "fixture-admin-token",
        }
    )
    client = app.test_client()

    caplog.set_level(logging.INFO)

    response = client.get(
        "/admin?user_id=1",
        headers={"Authorization": "Bearer fixture-admin-token"},
    )

    assert response.status_code == 200
    assert "Bearer fixture-admin-token" not in caplog.text
    assert "fixture-admin-token" not in caplog.text
    assert "Authorization" not in caplog.text
    assert "admin@example.com" not in caplog.text
