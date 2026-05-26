from __future__ import annotations

import os


LOCAL_ADMIN_BEARER_TOKEN = os.environ.get("LOCAL_ADMIN_BEARER_TOKEN", "local-admin-token")


USERS = [
    {
        "id": 1,
        "email": "admin@example.com",
        "name": "Admin User",
        "role": "admin",
    },
    {
        "id": 2,
        "email": "user@example.com",
        "name": "Regular User",
        "role": "user",
    },
]
