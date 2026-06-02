from flask import jsonify
from services import get_user_summary, get_admin_report

def register_routes(app):
    @app.route('/user/<int:user_id>/summary')
    def user_summary(user_id):
        try:
            summary = get_user_summary(user_id)
            return jsonify(summary)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    @app.route('/admin/report')
    def admin_report():
        report = get_admin_report()
        return jsonify(report)
