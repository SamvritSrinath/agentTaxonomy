from flask import jsonify

# Non-goal: We do not implement HTML rendering or template engines.
# This API-only view layer formats responses as JSON.

class UserView:
    @staticmethod
    def render_user(user):
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({
            "id": user["id"],
            "email": user["email"],
            "role": user["role"]
        })

    @staticmethod
    def render_user_list(users):
        return jsonify([
            {
                "id": u["id"],
                "email": u["email"],
                "role": u["role"]
            } for u in users
        ])

    @staticmethod
    def render_error(message, status_code=400):
        return jsonify({"error": message}), status_code

    @staticmethod
    def render_success(message, data=None):
        response = {"message": message}
        if data is not None:
            response["data"] = data
        return jsonify(response)
