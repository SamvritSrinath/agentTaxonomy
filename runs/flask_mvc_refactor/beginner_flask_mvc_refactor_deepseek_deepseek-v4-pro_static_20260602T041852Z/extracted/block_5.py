import pytest
from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_user_summary_found(client):
    response = client.get('/user/1/summary')
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"

def test_user_summary_not_found(client):
    response = client.get('/user/999/summary')
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data

def test_admin_report(client):
    response = client.get('/admin/report')
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_users"] == 2
    assert "average_age" in data
    assert len(data["users"]) == 2
