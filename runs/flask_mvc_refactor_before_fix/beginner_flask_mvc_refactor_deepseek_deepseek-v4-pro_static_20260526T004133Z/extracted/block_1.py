from flask import Flask, jsonify
from services.user_service import UserService
from services.report_service import ReportService

app = Flask(__name__)

# Dummy data
users = {
    "alice": {"name": "Alice", "posts": 5, "likes": 20},
    "bob": {"name": "Bob", "posts": 3, "likes": 15},
}

user_service = UserService(users)
report_service = ReportService(users)

@app.route('/user/<username>/summary')
def user_summary(username):
    result = user_service.get_user_summary(username)
    if result is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(result)

@app.route('/admin/report')
def admin_report():
    result = report_service.generate_report()
    return jsonify(result)

if __name__ == '__main__':
    app.run()
