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
