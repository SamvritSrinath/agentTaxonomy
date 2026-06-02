from __future__ import annotations

import logging
from typing import Any

from flask import Flask

from repositories import (
    ADMIN_TOKEN,
    ORDERS,
    USERS,
    InMemoryOrderRepository,
    InMemoryUserRepository,
)
from services import AdminReportService, UserSummaryService
from views import create_routes


def create_app() -> Flask:
    app = Flask(__name__)

    user_repository = InMemoryUserRepository(USERS)
    order_repository = InMemoryOrderRepository(ORDERS)

    user_summary_service = UserSummaryService(
        user_repository=user_repository,
        order_repository=order_repository,
    )
    admin_report_service = AdminReportService(
        user_repository=user_repository,
        order_repository=order_repository,
        admin_token=ADMIN_TOKEN,
    )

    app.register_blueprint(
        create_routes(
            user_summary_service=user_summary_service,
            admin_report_service=admin_report_service,
        )
    )

    return app


app = create_app()


@app.after_request
def _add_default_json_headers(response: Any) -> Any:
    """Keep responses predictable for tests and local clients."""
    if response.content_type == "application/json":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


logging.getLogger(__name__).addHandler(logging.NullHandler())


if __name__ == "__main__":
    app.run(debug=True)
