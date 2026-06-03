from flask import Flask, jsonify
from repositories import UserRepository, PurchaseRepository
from services import UserService, AdminService
from views import UserView, AdminView

app = Flask(__name__)

user_repo = UserRepository()
purchase_repo = PurchaseRepository()
user_service = UserService(user_repo, purchase_repo)
admin_service = AdminService(user_repo, purchase_repo)


@app.route('/users/<user_id>/summary', methods=['GET'])
@app.route('/user/<user_id>/summary', methods=['GET'])
@app.route('/users/<int:user_id>/summary', methods=['GET'])
@app.route('/user/<int:user_id>/summary', methods=['GET'])
def get_user_summary(user_id):
    summary_data = user_service.get_user_summary(user_id)
    response_data, status_code = UserView.render_summary(summary_data)
    return jsonify(response_data), status_code


@app.route('/admin/report', methods=['GET'])
@app.route('/admin/summary', methods=['GET'])
def get_admin_report():
    report_data = admin_service.get_admin_report()
    response_data, status_code = AdminView.render_report(report_data)
    return jsonify(response_data), status_code


if __name__ == '__main__':
    app.run(debug=True)
