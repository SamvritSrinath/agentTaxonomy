class UserView:
    @staticmethod
    def render_summary(summary_data):
        if summary_data is None:
            return {"error": "User not found"}, 404
        return summary_data, 200


class AdminView:
    @staticmethod
    def render_report(report_data):
        return report_data, 200
