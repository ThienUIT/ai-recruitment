"""Console route registration for the Talent Intelligence extension.

The registrar is safe to call unconditionally from Dify core. It evaluates the
feature flag before importing controller implementations, so disabled
deployments expose no Talent Intelligence routes.
"""

from flask_restx import Namespace

from configs import dify_config


def register_console_routes(namespace: Namespace) -> bool:
    """Register Talent Intelligence console routes when the feature is enabled.

    Returns whether routes were registered. The return value exists to make the
    feature gate directly testable without inspecting Flask-RESTX internals.
    """

    if not dify_config.TALENT_INTELLIGENCE_ENABLED:
        return False

    from ..documents import PIIEncryptionProvider

    PIIEncryptionProvider.from_json(
        dify_config.TI_PII_ENCRYPTION_KEYS_JSON,
        dify_config.TI_PII_ACTIVE_KEY_VERSION,
    )

    from .health import register_health_route
    from .resources import register_domain_routes, register_error_handlers

    register_error_handlers(namespace)
    register_health_route(namespace)
    register_domain_routes(namespace)
    return True


__all__ = ["register_console_routes"]
