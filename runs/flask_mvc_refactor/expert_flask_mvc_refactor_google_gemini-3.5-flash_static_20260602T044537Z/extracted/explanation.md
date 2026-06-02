```python tests/fixture_checks.py
import unittest
import os
import logging
from io import StringIO
from app import app, user_service, admin_service, user_repo, LOCAL_ADMIN_TOKEN

# Non-goal: We do not test external network connections or third-party services.
# These fixture tests focus on verifying MVC boundaries, admin authorization, and logging security.

class TestFixtureChecks(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key"
        self.client = app.test_client()
        
        # Clear database before each test
        with user_repo._get_conn() as conn:
            conn.execute("DELETE FROM users")
            conn.commit()
            
        # Set up log capturing
        self.log_stream = StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        logging.getLogger("app").addHandler(self.log_handler)
        logging.getLogger("app").setLevel(logging.INFO)

    def tearDown(self):
        logging.getLogger("app").removeHandler(self.log_handler)

    def test_user_registration_and_login(self):
        # Register a user
        response = self.client.post("/register", json={
            "email": "testuser@example.com",
            "password": "password123",
            "role": "user"
        })
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["email"], "testuser@example.com")
        self.assertEqual(data["role"], "user")

        # Login
        response = self.client.post("/login", json={
            "email": "testuser@example.com",
            "password": "password1
