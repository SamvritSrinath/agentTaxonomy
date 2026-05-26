import pytest
from app import app


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


def test_user_summary_found(client):
    resp = client.get('/user/alice/summary')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'summary' in data
    assert 'Alice' in data['summary']


def test_user_summary_not_found(client):
    resp = client.get('/user/nonexistent/summary')
    assert resp.status_code == 404
    data = resp.get_json()
    assert data['error'] == 'User not found'


def test_admin_report(client):
    resp = client.get('/admin/report')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'report' in data
