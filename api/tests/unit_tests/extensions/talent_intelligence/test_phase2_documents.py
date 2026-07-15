import base64
import io
import json
import zipfile

import pytest
from cryptography.exceptions import InvalidTag
from pypdf import PdfWriter

from extensions.talent_intelligence.documents import (
    FileValidationPolicy,
    LocalDocumentParser,
    LocalPIIRecognizer,
    PIIEncryptionProvider,
    PIIMasker,
    RequiresOCRError,
    detect_masked_leaks,
    validate_upload,
)
from extensions.talent_intelligence.documents.encryption import EncryptionConfigurationError
from extensions.talent_intelligence.errors import ConflictError, PayloadTooLargeError, UnsupportedMediaTypeError
from extensions.talent_intelligence.models import CandidateDocument, CandidateDocumentStatus
from extensions.talent_intelligence.services.documents import assert_document_safe_for_downstream


def _policy() -> FileValidationPolicy:
    return FileValidationPolicy(max_size_bytes=1024 * 1024, max_docx_uncompressed_bytes=1024 * 1024)


def _docx(text: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>",
        )
    return output.getvalue()


def test_validation_accepts_txt_and_docx_and_never_returns_filename() -> None:
    text = validate_upload(b"hello", "candidate.txt", "text/plain", _policy())
    document = validate_upload(
        _docx("hello"),
        "candidate.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _policy(),
    )
    assert (text.extension, text.mime_type) == (".txt", "text/plain")
    assert document.extension == ".docx"
    assert "candidate" not in repr(text)


@pytest.mark.parametrize(
    ("data", "filename", "content_type"),
    [
        (b"MZ\x90\x00", "resume.exe", "application/octet-stream"),
        (b"plain", "resume.pdf", "application/pdf"),
        (b"<html>bad</html>", "resume.html", "text/html"),
    ],
)
def test_validation_rejects_binary_signature_mismatch_and_unsupported_mime(
    data: bytes, filename: str, content_type: str
) -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        validate_upload(data, filename, content_type, _policy())


def test_validation_rejects_size_and_docx_zip_bomb() -> None:
    with pytest.raises(PayloadTooLargeError):
        validate_upload(b"a" * 20, "resume.txt", "text/plain", FileValidationPolicy(10, 100))
    with pytest.raises(PayloadTooLargeError):
        validate_upload(_docx("a" * 2000), "resume.docx", None, FileValidationPolicy(100_000, 100))


def test_local_txt_and_docx_parsers() -> None:
    parser = LocalDocumentParser(max_pdf_pages=10, max_text_chars=10_000)
    assert parser.parse(b"first\nsecond", ".txt").text == "first\nsecond"
    assert parser.parse(_docx("Local only"), ".docx").text == "Local only"


def test_image_only_pdf_requires_ocr_without_implementing_ocr() -> None:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    with pytest.raises(RequiresOCRError):
        LocalDocumentParser(max_pdf_pages=10, max_text_chars=10_000).parse(output.getvalue(), ".pdf")


def test_vietnamese_and_english_pii_is_stably_masked() -> None:
    text = (
        "Họ tên: Nguyễn Văn An\nEmail: an@example.com\nPhone: 0901234567\n"
        "LinkedIn: https://linkedin.com/in/nguyenvanan\nAgain: an@example.com"
    )
    entities = LocalPIIRecognizer().recognize(text)
    masked = PIIMasker().mask(text, entities)
    assert masked.text.count("[EMAIL_1]") == 2
    assert "Nguyễn Văn An" not in masked.text
    assert "0901234567" not in masked.text
    assert masked.entity_counts["PERSON"] == 1
    assert detect_masked_leaks(masked.text).safe


def test_independent_leak_detector_blocks_high_confidence_pii() -> None:
    result = detect_masked_leaks("Preserved: leak@example.com and 0901234567")
    assert not result.safe
    assert result.high_confidence_count == 2


def test_aes_gcm_has_random_nonce_aad_tamper_detection_and_rotation() -> None:
    key_v1 = b"1" * 32
    key_v2 = b"2" * 32
    provider = PIIEncryptionProvider({"v1": key_v1, "v2": key_v2}, "v2")
    aad = provider.aad("tenant-a", "candidate-a", "email")
    first = provider.encrypt("secret@example.com", aad=aad)
    second = provider.encrypt("secret@example.com", aad=aad)
    assert first != second
    assert "secret@example.com" not in first
    assert provider.decrypt(first, aad=aad) == "secret@example.com"
    assert json.loads(first)["key_version"] == "v2"
    with pytest.raises(InvalidTag):
        provider.decrypt(first, aad=provider.aad("tenant-b", "candidate-a", "email"))


def test_encryption_config_requires_active_32_byte_base64_key() -> None:
    encoded = base64.b64encode(b"short").decode()
    with pytest.raises(EncryptionConfigurationError):
        PIIEncryptionProvider.from_json(json.dumps({"v1": encoded}), "v1")


def test_privacy_gate_requires_ready_non_reviewed_masked_artifact() -> None:
    document = CandidateDocument(
        tenant_id="00000000-0000-0000-0000-000000000001",
        candidate_id="00000000-0000-0000-0000-000000000002",
        mime_type="text/plain",
        file_extension=".txt",
        size_bytes=5,
        sha256="a" * 64,
        uploaded_by="00000000-0000-0000-0000-000000000003",
    )
    with pytest.raises(ConflictError):
        assert_document_safe_for_downstream(document)
    document.status = CandidateDocumentStatus.READY
    document.masked_artifact_object_key = "private/internal/key"
    assert_document_safe_for_downstream(document)
