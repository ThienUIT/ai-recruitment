"""Secure local CV ingestion providers."""

from .encryption import PIIEncryptionProvider
from .malware import ClamAVScanner, MalwareScanResult
from .masking import LeakDetectionResult, LocalPIIRecognizer, MaskingResult, PIIMasker, detect_masked_leaks
from .parsers import LocalDocumentParser, ParsedDocument, RequiresOCRError
from .validation import FileValidationPolicy, ValidatedUpload, validate_upload

__all__ = [
    "ClamAVScanner",
    "FileValidationPolicy",
    "LeakDetectionResult",
    "LocalDocumentParser",
    "LocalPIIRecognizer",
    "MalwareScanResult",
    "MaskingResult",
    "PIIEncryptionProvider",
    "PIIMasker",
    "ParsedDocument",
    "RequiresOCRError",
    "ValidatedUpload",
    "detect_masked_leaks",
    "validate_upload",
]
