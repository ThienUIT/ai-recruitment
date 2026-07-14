"""Runtime registration and access tests for Talent Intelligence health."""

from unittest.mock import MagicMock

import pytest
from flask import Blueprint
from flask_restx import Api, Namespace

from configs import dify_config
from dify_app import DifyApp
from extensions import ext_login
from extensions.talent_intelligence.controllers import register_console_routes
from models import Account


def _build_app(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> tuple[DifyApp, bool]:
    monkeypatch.setattr(dify_config, "TALENT_INTELLIGENCE_ENABLED", enabled)

    app = DifyApp(__name__)
    app.config.update(
        LOGIN_DISABLED=False,
        RESTX_MASK_HEADER="X-Fields",
        RESTX_MASK_SWAGGER=False,
        SECRET_KEY="test-only-secret",
        TESTING=True,
    )
    ext_login.init_app(app)

    blueprint = Blueprint("console", __name__, url_prefix="/console/api")
    api = Api(blueprint)
    namespace = Namespace("console", path="/")
    registered = register_console_routes(namespace)
    api.add_namespace(namespace)
    app.register_blueprint(blueprint)
    return app, registered


def test_health_route_is_registered_when_feature_is_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    app, registered = _build_app(monkeypatch, enabled=True)

    assert registered is True
    assert any(rule.rule == "/console/api/talent-intelligence/health" for rule in app.url_map.iter_rules())


def test_health_route_is_absent_when_feature_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    app, registered = _build_app(monkeypatch, enabled=False)

    response = app.test_client().get("/console/api/talent-intelligence/health")

    assert registered is False
    assert response.status_code == 404


def test_health_route_rejects_unauthenticated_request(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    monkeypatch.setattr("libs.login._resolve_current_user", lambda: None)

    response = app.test_client().get("/console/api/talent-intelligence/health")

    assert response.status_code == 401
    assert response.get_json() == {"code": "unauthorized", "message": "Unauthorized."}


def test_health_route_resolves_authenticated_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    account = MagicMock(spec=Account)
    account.id = "account-123"
    account.is_authenticated = True
    resolved_tenants: list[str] = []

    monkeypatch.setattr("libs.login._resolve_current_user", lambda: account)
    monkeypatch.setattr("libs.login.check_csrf_token", lambda *_: None)

    def resolve_account() -> tuple[Account, str]:
        resolved_tenants.append("tenant-123")
        return account, "tenant-123"

    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.health.current_account_with_tenant",
        resolve_account,
    )

    response = app.test_client().get("/console/api/talent-intelligence/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "module": "talent_intelligence",
        "enabled": True,
        "version": "0.1.0",
    }
    assert resolved_tenants == ["tenant-123"]
