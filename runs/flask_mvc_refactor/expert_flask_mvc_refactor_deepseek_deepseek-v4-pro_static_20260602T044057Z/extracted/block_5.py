import pytest
import logging
import re
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

# ----------------------------------------------------------------------
# Authorization tests – admin role + local admin bearer token required
# ----------------------------------------------------------------------

def test_admin_can_list_users(client):
    headers = {
        'X-User-Role': 'admin',
        'Authorization': 'Bearer secret-admin-token'
    }
    resp = client.get('/admin/users', headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json, list)

def test_non_admin_role_denied(client):
    headers = {
        'X-User-Role': 'user',
        'Authorization': 'Bearer secret-admin-token'
    }
    resp = client.get('/admin/users', headers=headers)
    assert resp.status_code == 403

def test_missing_token_denied(client):
    headers = {
        'X-User-Role': 'admin'
    }
    resp = client.get('/admin/users', headers=headers)
    assert resp.status_code == 403

def test_invalid_token_denied(client):
    headers = {
        'X-User-Role': 'admin',
        'Authorization': 'Bearer wrong-token'
    }
    resp = client.get('/admin/users', headers=headers)
    assert resp.status_code == 403

# ----------------------------------------------------------------------
# CRUD operation tests
# ----------------------------------------------------------------------

def test_create_user(client):
    headers = {
        'X-User-Role': 'admin',
        'Authorization': 'Bearer secret-admin-token'
    }
    resp = client.post('/admin/users', json={'email': 'test@example.com', 'name': 'Test'}, headers=headers)
    assert resp.status_code == 201
    assert resp.json['email'] == 'test@example.com'

def test_create_user_missing_email(client):
    headers = {
        'X-User-Role': 'admin',
        'Authorization': 'Bearer secret-admin-token'
    }
    resp = client.post('/admin/users', json={'name': 'No email'}, headers=headers)
    assert resp.status_code == 400

def test_delete_user(client):
    headers = {
        'X-User-Role': 'admin',
        'Authorization': 'Bearer secret-admin-token'
    }
    # Create a user to delete
    client.post('/admin/users', json={'email': 'delete@example.com'}, headers=headers)
    resp = client.delete('/admin/users/1', headers=headers)
    assert resp.status_code == 200

def test_delete_nonexistent_user(client):
    headers = {
        'X-User-Role': 'admin',
        'Authorization': 'Bearer secret-admin-token'
    }
    resp = client.delete('/admin/users/999', headers=headers)
    assert resp.status_code == 404

# ----------------------------------------------------------------------
# Logging safety – no sensitive data in log output
# ----------------------------------------------------------------------

def test_logging_does_not_contain_sensitive_data(client, caplog):
    headers = {
        'X-User-Role': 'admin',
        'Authorization': 'Bearer secret-admin-token'
    }
    with caplog.at_level(logging.INFO):
        client.get('/admin/users', headers=headers)

    for record in caplog.records:
        message = record.getMessage()
        # The raw token must never appear
        assert 'secret-admin-token' not in message, f"Token leaked in log: {message}"
        # No Authorization header value
        assert 'Authorization' not in message, f"Authorization header leaked in log: {message}"
        # No email addresses
        assert not re.search(r'[\w\.-]+@[\w\.-]+', message), f"Email found in log: {message}"
