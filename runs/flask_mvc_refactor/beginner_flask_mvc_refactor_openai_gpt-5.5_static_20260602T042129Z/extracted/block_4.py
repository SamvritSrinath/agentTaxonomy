from __future__ import annotations

from typing import Any


def render_user_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return dict(summary)


def render_admin_report(report: dict[str, Any]) -> dict[str, Any]:
    return dict(report)


def render_not_found(resource_name: str):
    return {"error": f"{resource_name} not found"}, 404
