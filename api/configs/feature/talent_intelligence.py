"""Feature flags for the optional Talent Intelligence domain extension."""

from pydantic import Field
from pydantic_settings import BaseSettings


class TalentIntelligenceConfig(BaseSettings):
    """Control whether Talent Intelligence integration points may be registered."""

    TALENT_INTELLIGENCE_ENABLED: bool = Field(
        default=False,
        description="Enable the privacy-first Talent Intelligence domain extension.",
    )
