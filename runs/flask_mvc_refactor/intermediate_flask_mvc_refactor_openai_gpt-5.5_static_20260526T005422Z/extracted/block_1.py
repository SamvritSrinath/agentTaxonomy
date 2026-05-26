from __future__ import annotations

import logging
from typing import Optional

from flask import Flask

from repositories import InMemoryReportRepository, ORDERS, USERS
from routes import register_routes
from services import ReportService

logger = logging.getLogger(__name__)


def create_app(
    repository: Optional[InMemoryReportRepository] = None,
    service: Optional[ReportService] = None,
) -> Flask:
    app = Flask(__name__)

    report_repository = repository or InMemoryReportRepository()
    report_service = service or ReportService(report_repository)

    register_routes(app, report_service)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
