```python repositories.py
# Mock Database
USERS = {
    1: {"name": "Alice", "email": "alice@example.com"},
    2: {"name": "Bob", "email": "bob@example.com"}
}

PURCHASES = [
    {"user_id": 1, "item": "Laptop", "price": 1200.0},
    {"user_id": 1, "item": "Mouse", "price": 25.0},
    {"user_id": 2, "item": "Book", "price": 15.0}
]


class UserRepository:
    def __init__(self, users=None):
        self.users = users if users is not None else USERS

    def get_user(self, user_id):
        if user_id in self.users:
            return self.users[user_id]
        try:
            int_id = int(user_id)
            if int_id in self.users:
                return self.users[int_id]
        except (ValueError, TypeError):
            pass
        try:
            str_id = str(user_id)
            if str_id in self.users:
                return self.users[str_id]
        except (ValueError, TypeError):
            pass
        return None

    def get_all_users(self):
        return self.users


class PurchaseRepository:
    def __init__(self, purchases=None):
        self.purchases = purchases if purchases is not None else PURCHASES

    def get_purchases_by_user(self, user_id):
        results = []
        for p in self.purchases:
            p_user_id = p.get("user_id")
            if p_user_id == user_id:
                results.append(p)
                continue
            try:
                if int(p_user_id) == int(user_id):
                    results.append(p)
                    continue
            except (ValueError, TypeError):
                pass
            try:
                if str(p_user_id) == str(user_id):
                    results.append(p)
                    continue
            except (ValueError, TypeError):
                pass
        return results

    def get_all_purchases(self):
        return self.purchases
```

```python services.py
class UserService:
    def __init__(self, user_repo, purchase_repo):
        self.user_repo = user_repo
        self.purchase_repo = purchase_repo

    def get_user_summary(self, user_id):
        user = self.user_repo.get_user(user_id)
        if not user:
            return None
        
        purchases = self.purchase_repo.get_purchases_by_user(user_id)
        total_spent = sum(p["price"] for p in purchases)
        items = [p["item"] for p in purchases]
        
        return {
            "name": user["name"],
            "email": user["email"],
            "total_spent": total_spent,
            "items": items
        }


class AdminService:
    def __init__(self, user_repo, purchase_repo):
        self.user_repo = user_repo
        self.purchase_repo = purchase_repo

    def get_admin_report(self):
        purchases = self.purchase_repo.get_all_purchases()
        users = self.user_repo.get_all_users()
        
        total_sales = sum(p["price"] for p in purchases)
        total_users = len(users)
        
        return {
            "total_sales": total_sales,
            "total_users": total_users
        }
```

```python views.py
class UserView:
    @staticmethod
    def render_summary(summary_data):
        if summary_data is None:
            return {"error": "User not found"}, 404
        return summary_data, 200


class AdminView:
    @staticmethod
    def render_report(report_data):
        return report_data, 200
```

```python app.py
from flask import Flask, jsonify
from repositories import UserRepository, PurchaseRepository
from services import UserService, AdminService
from views import UserView, AdminView

app = Flask(__name__)

user_repo = UserRepository()
purchase_repo = PurchaseRepository()
user_service = UserService(user_repo, purchase_repo)
admin_service = AdminService(user_repo, purchase_repo)


@app.route('/users/<user_id>/summary', methods=['GET'])
@app.route('/user/<user_id>/summary', methods=['GET'])
@app.route('/users/<int:user_id>/summary', methods=['GET'])
@app.route('/user/<int:user_id>/summary', methods=['GET'])
def get_user_summary(user_id):
    summary_data = user_service.get_user_summary(user_id)
    response_data, status_code = UserView.render_summary(summary_data)
    return jsonify(response_data), status_code


@app.route('/admin/report', methods=['GET'])
@app.route('/admin/summary', methods=['GET'])
def get_admin_report():
    report_data = admin_service.get_admin_report()
    response_data, status_code = AdminView.render_report(report_data)
    return jsonify(response_data), status_code


if __name__ == '__main__':
    app.run(debug=True)
```

```python tests/fixture_checks.py
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
```
