from __future__ import annotations

import logging
from flask import Flask, request, jsonify

# Added basic logging config so the logger.info actually prints to the console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

USERS = {
    "ada@example.com": {"name": "Ada", "role": "admin"},
    "lin@example.com": {"name": "Lin", "role": "analyst"},
}

def require_admin(headers: dict[str, str]) -> bool:
    """Return whether the caller is allowed to read admin reports."""
    return headers.get("X-Role") == "admin" and headers.get("Authorization") == "Bearer local-admin"


def user_summary(email: str, headers: dict[str, str]) -> dict[str, str]:
    """Return a display summary for a user."""
    logger.info("loading user %s with headers %s", email, headers)
    user = USERS[email]
    return {"email": email, "display": f"{user['name']} ({user['role']})"}


def admin_report(headers: dict[str, str]) -> dict[str, object]:
    """Return an admin-only report."""
    if not require_admin(headers):
        return {"status": 403, "error": "forbidden"}
    return {"status": 200, "users": sorted(USERS)}

# ==========================================
# FLASK ROUTE WRAPPERS 
# ==========================================

@app.route('/summary/<email>', methods=['GET'])
def get_user_summary(email):
    # Flask's request.headers is a special object; cast to standard dict to match your type hints
    headers = dict(request.headers)
    
    try:
        # Call your untouched function
        result = user_summary(email, headers)
        return jsonify(result), 200
    except KeyError:
        # Prevent the app from crashing if the email isn't in the USERS dict
        return jsonify({"error": "user not found"}), 404

@app.route('/admin/report', methods=['GET'])
def get_admin_report():
    headers = dict(request.headers)
    
    # Call your untouched function
    result = admin_report(headers)
    
    # Extract the status code from your function's dictionary return
    status_code = result.get("status", 200)
    return jsonify(result), status_code

if __name__ == '__main__':
    # Run on http://127.0.0.1:5000
    app.run(debug=True)