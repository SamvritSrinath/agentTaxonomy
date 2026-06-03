from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_route_layer_delegates_to_services():
    app_source = read_repo_file("app.py")
    views_source = read_repo_file("views.py")

    assert "UserSummaryService" in app_source
    assert "AdminReportService" in app_source
    assert "create_routes" in app_source
    assert "user_summary_service.get_summary" in views_source
    assert "admin_report_service.build_report" in views_source


def test_repositories_and_services_are_separate_modules():
    assert "class InMemoryUserRepository" in read_repo_file("repositories.py")
    assert "class InMemoryOrderRepository" in read_repo_file("repositories.py")
    assert "class UserSummaryService" in read_repo_file("services.py")
    assert "class AdminReportService" in read_repo_file("services.py")


def test_sensitive_values_are_not_logged():
    combined_source = "\n".join(
        read_repo_file(path)
        for path in ("app.py", "views.py", "services.py", "repositories.py")
    )

    assert "logger.info(request.headers" not in combined_source
    assert "Authorization" in combined_source
    assert "authorization_present" in combined_source
    assert "email" not in read_repo_file("views.py").lower()
