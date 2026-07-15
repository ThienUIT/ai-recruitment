"""Runtime registration and access tests for Talent Intelligence health."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Blueprint
from flask_restx import Namespace

from configs import dify_config
from dify_app import DifyApp
from extensions import ext_login
from extensions.talent_intelligence.controllers import register_console_routes
from extensions.talent_intelligence.errors import NotFoundError
from libs.external_api import ExternalApi
from models import Account


def _build_app(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> tuple[DifyApp, bool]:
    monkeypatch.setattr(dify_config, "TALENT_INTELLIGENCE_ENABLED", enabled)
    if enabled:
        monkeypatch.setattr(dify_config, "TI_PII_ACTIVE_KEY_VERSION", "v1")
        monkeypatch.setattr(
            dify_config,
            "TI_PII_ENCRYPTION_KEYS_JSON",
            '{"v1":"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="}',
        )

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
    api = ExternalApi(blueprint)
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


def _authenticate(monkeypatch: pytest.MonkeyPatch, account: MagicMock) -> None:
    account.is_authenticated = True
    monkeypatch.setattr("libs.login._resolve_current_user", lambda: account)
    monkeypatch.setattr("libs.login.check_csrf_token", lambda *_: None)
    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.resources.current_account_with_tenant",
        lambda: (account, "tenant-123"),
    )


def test_domain_route_rejects_unauthenticated_request(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    monkeypatch.setattr("libs.login._resolve_current_user", lambda: None)

    response = app.test_client().get("/console/api/talent-intelligence/candidates")

    assert response.status_code == 401


def test_domain_route_rejects_insufficient_workspace_role(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    account = MagicMock(spec=Account)
    account.has_edit_permission = False
    account.is_admin_or_owner = False
    _authenticate(monkeypatch, account)

    response = app.test_client().post(
        "/console/api/talent-intelligence/candidates",
        json={"external_reference": "ATS-001"},
    )

    assert response.status_code == 403


def test_domain_route_rejects_unknown_candidate_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    account = MagicMock(spec=Account)
    account.has_edit_permission = True
    account.is_admin_or_owner = False
    _authenticate(monkeypatch, account)

    response = app.test_client().post(
        "/console/api/talent-intelligence/candidates",
        json={"raw_cv": "must not be accepted"},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Request validation failed."


def test_authenticated_tenant_can_list_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    account = MagicMock(spec=Account)
    account.has_edit_permission = False
    account.is_admin_or_owner = False
    _authenticate(monkeypatch, account)

    class SessionContext:
        def __enter__(self):
            return MagicMock()

        def __exit__(self, *_args: object) -> None:
            return None

    class CandidateServiceStub:
        def __init__(self, _session: object) -> None:
            pass

        def list(self, tenant_id: str, *, page: int, limit: int):
            assert tenant_id == "tenant-123"
            return [], 0

    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.resources.db",
        SimpleNamespace(engine=object()),
    )
    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.resources.Session",
        lambda *_args, **_kwargs: SessionContext(),
    )
    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.resources.CandidateService",
        CandidateServiceStub,
    )

    response = app.test_client().get("/console/api/talent-intelligence/candidates?page=1&limit=10")

    assert response.status_code == 200
    assert response.get_json() == {"data": [], "page": 1, "limit": 10, "total": 0}


def test_audit_route_requires_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    account = MagicMock(spec=Account)
    account.has_edit_permission = True
    account.is_admin_or_owner = False
    _authenticate(monkeypatch, account)

    response = app.test_client().get("/console/api/talent-intelligence/audit")

    assert response.status_code == 403


def test_tenant_scoped_missing_object_uses_dify_http_error_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = _build_app(monkeypatch, enabled=True)
    account = MagicMock(spec=Account)
    account.has_edit_permission = False
    account.is_admin_or_owner = False
    _authenticate(monkeypatch, account)

    class SessionContext:
        def __enter__(self):
            return MagicMock()

        def __exit__(self, *_args: object) -> None:
            return None

    class CandidateServiceStub:
        def __init__(self, _session: object) -> None:
            pass

        def get(self, tenant_id: str, candidate_id: str):
            raise NotFoundError("Candidate not found.")

    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.resources.db",
        SimpleNamespace(engine=object()),
    )
    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.resources.Session",
        lambda *_args, **_kwargs: SessionContext(),
    )
    monkeypatch.setattr(
        "extensions.talent_intelligence.controllers.resources.CandidateService",
        CandidateServiceStub,
    )

    response = app.test_client().get("/console/api/talent-intelligence/candidates/foreign-id")

    assert response.status_code == 404
