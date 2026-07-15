"""Configuration for the optional Talent Intelligence domain extension."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class TalentIntelligenceConfig(BaseSettings):
    """Control whether Talent Intelligence integration points may be registered."""

    TALENT_INTELLIGENCE_ENABLED: bool = Field(
        default=False,
        description="Enable the privacy-first Talent Intelligence domain extension.",
    )
    TI_MAX_CV_SIZE_MB: int = Field(default=10, ge=1, le=100)
    TI_MAX_PDF_PAGES: int = Field(default=50, ge=1, le=500)
    TI_MAX_DOCX_UNCOMPRESSED_MB: int = Field(default=50, ge=1, le=500)
    TI_MAX_EXTRACTED_TEXT_CHARS: int = Field(default=500_000, ge=1_000, le=5_000_000)
    TI_MALWARE_SCAN_ENABLED: bool = True
    TI_CLAMAV_HOST: str = "clamav"
    TI_CLAMAV_PORT: int = Field(default=3310, ge=1, le=65535)
    TI_ALLOW_UNSCANNED_UPLOADS_IN_DEVELOPMENT: bool = False
    TI_RAW_CV_RETENTION_DAYS: int = Field(default=7, ge=0, le=7)
    TI_DELETE_RAW_CV_AFTER_EXTRACTION: bool = False
    TI_TEMP_ARTIFACT_RETENTION_HOURS: int = Field(default=24, ge=1, le=168)
    TI_MASK_COMPANY_NAMES: bool = False
    TI_PII_REVIEW_THRESHOLD: float = Field(default=0.70, ge=0, le=1)
    TI_PII_ACTIVE_KEY_VERSION: str = "v1"
    TI_PII_ENCRYPTION_KEYS_JSON: str = "{}"

    @field_validator("TI_CLAMAV_HOST", "TI_PII_ACTIVE_KEY_VERSION")
    @classmethod
    def _require_nonempty_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value
