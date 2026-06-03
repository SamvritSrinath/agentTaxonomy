from __future__ import annotations

try:
    from flask import Flask
except ImportError:  # pragma: no cover - keeps the module usable without Flask installed.
    class Flask:  # type: ignore[no-redef]
        def __init__(self, name: str) -> None:
            self.name = name

        def route(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

import repositories
from services import build_admin_report, build_user_summary
from views import render_admin_report, render_not_found, render_user_summary


app = Flask(__name__)

# Backwards-compatible access to the in-memory data used by the app.
USERS = repositories.USERS
ORDERS = repositories.ORDERS


@app.route("/users/<int:user_id>/summary")
@app.route("/user/<int:user_id>/summary")
@app.route("/user/<int:user_id>")
def user_summary(user_id: int):
    summary = build_user_summary(user_id)
    if summary is None:
        return render_not_found("User")

    return render_user_summary(summary)


@app.route("/admin/report")
def admin_report():
    report = build_admin_report()
    return render_admin_report(report)


if __name__ == "__main__":
    app.run(debug=True)
