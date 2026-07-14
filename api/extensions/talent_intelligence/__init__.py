"""Privacy-first recruitment decision-support extension for Dify.

The package owns recruitment-domain behavior and data. Generic Dify modules may
register or call this package, but domain rules must not move into those modules.
The feature is disabled by default through ``TALENT_INTELLIGENCE_ENABLED``.
"""

EXTENSION_NAME = "talent_intelligence"
EXTENSION_VERSION = "0.1.0"

__all__ = ["EXTENSION_NAME", "EXTENSION_VERSION"]
