"""Streaming-friendly CV type, signature, and archive validation."""

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from ..errors import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError

_PDF_MIME = "application/pdf"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_TXT_MIME = "text/plain"
_ALLOWED_CONTENT_TYPES = {_PDF_MIME, _DOCX_MIME, _TXT_MIME, "application/octet-stream"}


@dataclass(frozen=True)
class FileValidationPolicy:
    max_size_bytes: int
    max_docx_uncompressed_bytes: int


@dataclass(frozen=True)
class ValidatedUpload:
    data: bytes
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str


def _validate_docx(data: bytes, limit: int) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = {entry.filename for entry in archive.infolist()}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UnsupportedMediaTypeError("File is not a valid DOCX document.", code="unsupported_file_type")
            if any(name.lower().endswith(("vbaproject.bin", ".exe", ".dll")) for name in names):
                raise UnsupportedMediaTypeError("Macro-enabled documents are not supported.", code="active_content")
            if sum(entry.file_size for entry in archive.infolist()) > limit:
                raise PayloadTooLargeError("Expanded DOCX exceeds the configured limit.", code="archive_too_large")
            for entry in archive.infolist():
                path = PurePath(entry.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise ValidationError("DOCX contains an unsafe archive path.", code="unsafe_archive")
    except zipfile.BadZipFile as error:
        raise UnsupportedMediaTypeError("File is not a valid DOCX document.", code="invalid_docx") from error


def validate_upload(
    data: bytes,
    filename: str | None,
    content_type: str | None,
    policy: FileValidationPolicy,
) -> ValidatedUpload:
    """Validate bytes without persisting the potentially PII-bearing filename."""

    if not data:
        raise ValidationError("Uploaded document is empty.", code="empty_file")
    if len(data) > policy.max_size_bytes:
        raise PayloadTooLargeError("Uploaded document exceeds the configured limit.", code="file_too_large")
    claimed_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if claimed_type not in _ALLOWED_CONTENT_TYPES:
        raise UnsupportedMediaTypeError(
            "Only PDF, DOCX, and TXT documents are supported.", code="unsupported_file_type"
        )

    suffix = PurePath(filename or "").suffix.lower()
    if data.startswith(b"%PDF-"):
        detected_mime, extension = _PDF_MIME, ".pdf"
    elif data.startswith(b"PK\x03\x04"):
        _validate_docx(data, policy.max_docx_uncompressed_bytes)
        detected_mime, extension = _DOCX_MIME, ".docx"
    else:
        if b"\x00" in data[:8192]:
            raise UnsupportedMediaTypeError("Binary files are not supported.", code="binary_file")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise UnsupportedMediaTypeError(
                "Text document encoding is not supported.", code="unsupported_encoding"
            ) from error
        detected_mime, extension = _TXT_MIME, ".txt"

    if suffix and suffix != extension:
        raise UnsupportedMediaTypeError("Filename extension does not match file content.", code="signature_mismatch")
    if claimed_type not in {"application/octet-stream", detected_mime}:
        raise UnsupportedMediaTypeError("Declared MIME type does not match file content.", code="mime_mismatch")
    return ValidatedUpload(data, detected_mime, extension, len(data), hashlib.sha256(data).hexdigest())
