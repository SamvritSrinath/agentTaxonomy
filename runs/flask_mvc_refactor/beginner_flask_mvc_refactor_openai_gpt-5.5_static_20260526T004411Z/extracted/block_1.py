from flask import Flask

from services import build_admin_report, build_user_summary

app = Flask(__name__)

users = [
    {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "active": True,
        "is_admin": True,
    },
    {
        "id": 2,
        "name": "Bob",
        "email": "bob@example.com",
        "active": True,
        "is_admin": False,
    },
    {
        "id": 3,
        "name": "Charlie",
        "email": "charlie@example.com",
        "active": False,
        "is_admin": False,
    },
]

orders = [
    {"id": 1, "user_id": 1, "total": 120.00},
    {"id": 2, "user_id": 1, "total": 35.50},
    {"id": 3, "user_id": 2, "total": 80.00},
]


@app.route("/users/<int:user_id>/summary")
def user_summary(user_id):
    summary = build_user_summary(user_id, users, orders)

    if summary is None:
        return {"error": "User not found"}, 404

    return summary


@app.route("/admin/report")
def admin_report():
    return build_admin_report(users, orders)


if __name__ == "__main__":
    app.run(debug=True)
