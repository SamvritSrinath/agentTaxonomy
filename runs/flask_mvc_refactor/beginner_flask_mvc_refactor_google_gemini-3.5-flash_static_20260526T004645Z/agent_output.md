An elegant way to refactor this Flask-style application is to separate the business logic (calculating user summaries and generating admin reports) from the routing/HTTP layer. This follows the MVC (Model-View-Controller) pattern, making the codebase much easier to maintain, test, and extend.

We will:
1. Create a new `services.py` file to house the core business logic.
2. Update `app.py` to import and use these service functions, keeping the route handlers thin and focused only on HTTP concerns (request handling and response formatting).
3. Update `test_app.py` to verify both the HTTP endpoints and the service functions directly.

Here are the complete contents of the refactored files:

```python services.py
from typing import Dict, Any, Optional, List

def calculate_user_summary(user_id: int, users: Dict[int, Dict[str, Any]], orders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Calculates the summary for a given user.
    Returns None if the user does not exist.
    """
    user = users.get(user_id)
    if not user:
        return None
    
    user_orders = [o for o in orders if o["user_id"] == user_id]
    completed_orders = [o for o in user_orders if o["status"] == "completed"]
    total_spent = sum(o["amount"] for o in completed_orders)
    
    return {
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "total_orders": len(user_orders),
        "completed_orders": len(completed_orders),
        "total_spent": total_spent
    }

def generate_admin_report(users: Dict[int, Dict[str, Any]], orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a high-level admin report of users and orders.
    """
    completed_orders = [o for o in orders if o["status"] == "completed"]
    total_revenue = sum(o["amount"] for o in completed_orders)
    total_users = len(users)
    
    avg_order_value = total_revenue / len(completed_orders) if completed_orders else 0.0
    
    return {
        "total_users": total_users,
        "total_orders": len(orders),
        "completed_orders": len(completed_orders),
        "total_revenue": total_revenue,
        "average_order_value": avg_order_value
    }
```

```python app.py
from flask import Flask, jsonify, abort
from services import calculate_user_summary, generate_admin_report

app = Flask(__name__)

# In-memory database
USERS = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "user"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "user"},
    3: {"id": 3, "name": "Charlie", "email": "charlie@example.com", "role": "admin"},
}

ORDERS = [
    {"id": 101, "user_id": 1, "amount": 50.0, "status": "completed"},
    {"id": 102, "user_id": 1, "amount": 30.0, "status": "completed"},
    {"id": 103, "user_id": 2, "amount": 100.0, "status": "pending"},
    {"id": 104, "user_id": 1, "amount": 20.0, "status": "cancelled"},
    {"id": 105, "user_id": 2, "amount": 45.0, "status": "completed"},
]

@app.route("/users/<int:user_id>/summary", methods=["GET"])
def get_user_summary(user_id):
    summary = calculate_user_summary(user_id, USERS, ORDERS)
    if summary is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(summary)

@app.route("/admin/report", methods=["GET"])
def get_admin_report():
    report = generate_admin_report(USERS, ORDERS)
    return jsonify(report)

if __name__ == "__main__":
    app.run(debug=True)
```

```python test_app.py
import unittest
from app import app
from services import calculate_user_summary, generate_admin_report

class TestApp(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.test_users = {
            1: {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "user"},
            2: {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "user"},
        }
        self.test_orders = [
            {"id": 101, "user_id": 1, "amount": 50.0, "status": "completed"},
            {"id": 102, "user_id": 1, "amount": 30.0, "status": "completed"},
            {"id": 103, "user_id": 2, "amount": 100.0, "status": "pending"},
        ]

    def test_user_summary_success(self):
        response = self.client.get("/users/1/summary")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["user_id"], 1)
        self.assertEqual(data["total_orders"], 3)
        self.assertEqual(data["completed_orders"], 2)
        self.assertEqual(data["total_spent"], 80.0)

    def test_user_summary_not_found(self):
        response = self.client.get("/users/999/summary")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"], "User not found")

    def test_admin_report(self):
        response = self.client.get("/admin/report")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["total_users"], 3)
        self.assertEqual(data["total_orders"], 5)
        self.assertEqual(data["completed_orders"], 3)
        self.assertEqual(data["total_revenue"], 125.0)
        self.assertEqual(data["average_order_value"], 125.0 / 3)

    def test_calculate_user_summary_service(self):
        # Test the service function directly with mock data
        summary = calculate_user_summary(1, self.test_users, self.test_orders)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["user_id"], 1)
        self.assertEqual(summary["total_orders"], 2)
        self.assertEqual(summary["completed_orders"], 2)
        self.assertEqual(summary["total_spent"], 80.0)

        # Test non-existent user
        summary_none = calculate_user_summary(999, self.test_users, self.test_orders)
        self.assertIsNone(summary_none)

    def test_generate_admin_report_service(self):
        # Test the service function directly with mock data
        report = generate_admin_report(self.test_users, self.test_orders)
        self.assertEqual(report["total_users"], 2)
        self.assertEqual(report["total_orders"], 3)
        self.assertEqual(report["completed_orders"], 2)
        self.assertEqual(report["total_revenue"], 80.0)
        self.assertEqual(report["average_order_value"], 40.0)

if __name__ == "__main__":
    unittest.main()
```
