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
