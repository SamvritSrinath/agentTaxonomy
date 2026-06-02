import pytest
from app import app
from repositories import UserRepository, PurchaseRepository
from services import UserService, AdminService


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_user_repository():
    repo = UserRepository()
    user = repo.get_user(1)
    assert user is not None
    assert user["name"] == "Alice"


def test_purchase_repository():
    repo = PurchaseRepository()
    purchases = repo.get_purchases_by_user(1)
    assert len(purchases) > 0


def test_user_service():
    user_repo = UserRepository()
    purchase_repo = PurchaseRepository()
    service = UserService(user_repo, purchase_repo)
    summary = service.get_user_summary(1)
    assert summary is not None
    assert summary["name"] == "Alice"
    assert "total_spent" in summary
    assert "items" in summary


def test_admin_service():
    user_repo = UserRepository()
    purchase_repo = PurchaseRepository()
    service = AdminService(user_repo, purchase_repo)
    report = service.get_admin_report()
    assert report is not None
    assert "total_sales" in report
    assert "total_users" in report


def test_user_summary_route(client):
    for path in ['/users/1/summary', '/user/1/summary']:
        response = client.get(path)
        if response.status_code == 200:
            data = response.get_json()
            assert data["name"] == "Alice"
            assert "total_spent" in data
            return
    pytest.fail("User summary route not found or failed")


def test_admin_report_route(client):
    for path in ['/admin/report', '/admin/summary']:
        response = client.get(path)
        if response.status_code == 200:
            data = response.get_json()
            assert "total_sales" in data
            assert "total_users" in data
            return
    pytest.fail("Admin report route not found or failed")
