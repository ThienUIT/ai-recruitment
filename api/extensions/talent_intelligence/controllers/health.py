"""Authenticated, tenant-aware runtime health endpoint."""

from flask_restx import Namespace, Resource
from typing_extensions import TypedDict

from controllers.common.schema import register_response_schema_models
from fields.base import ResponseModel
from libs.helper import dump_response
from libs.login import current_account_with_tenant, login_required

from .. import EXTENSION_NAME, EXTENSION_VERSION


class TalentIntelligenceHealthResponse(ResponseModel):
    status: str
    module: str
    enabled: bool
    version: str


class HealthPayload(TypedDict):
    status: str
    module: str
    enabled: bool
    version: str


def register_health_route(namespace: Namespace) -> None:
    """Attach the health resource to Dify's console namespace."""

    register_response_schema_models(namespace, TalentIntelligenceHealthResponse)

    @namespace.route("/talent-intelligence/health")
    class TalentIntelligenceHealthApi(Resource):
        @namespace.doc("get_talent_intelligence_health")
        @namespace.doc(description="Verify the enabled Talent Intelligence module for the current tenant")
        @namespace.response(
            200,
            "Success",
            namespace.models[TalentIntelligenceHealthResponse.__name__],
        )
        @login_required
        def get(self) -> dict[str, object]:
            """Return module metadata after authentication and tenant resolution."""

            _, current_tenant_id = current_account_with_tenant()
            del current_tenant_id
            payload: HealthPayload = {
                "status": "ok",
                "module": EXTENSION_NAME,
                "enabled": True,
                "version": EXTENSION_VERSION,
            }
            return dump_response(TalentIntelligenceHealthResponse, payload)
