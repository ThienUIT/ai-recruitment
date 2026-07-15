"""Bounded local parsers that never persist extracted raw text."""

import io
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from pypdf import PdfReader


class DocumentParsingError(RuntimeError):
    pass


class RequiresOCRError(DocumentParsingError):
    pass


@dataclass(frozen=True)
class ParsedBlock:
    index: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    blocks: tuple[ParsedBlock, ...]
    parser_name: str
    parser_version: str
    page_count: int | None = None

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks)


class LocalDocumentParser:
    def __init__(self, *, max_pdf_pages: int, max_text_chars: int) -> None:
        self._max_pdf_pages = max_pdf_pages
        self._max_text_chars = max_text_chars

    def parse(self, data: bytes, extension: str) -> ParsedDocument:
        if extension == ".pdf":
            return self._parse_pdf(data)
        if extension == ".docx":
            return self._parse_docx(data)
        if extension == ".txt":
            return self._parse_txt(data)
        raise DocumentParsingError("Unsupported parser format.")

    def _bounded(self, blocks: list[str]) -> tuple[ParsedBlock, ...]:
        total = 0
        result: list[ParsedBlock] = []
        for text in blocks:
            normalized = re.sub(r"[ \t]+", " ", text).strip()
            total += len(normalized)
            if total > self._max_text_chars:
                raise DocumentParsingError("Extracted text exceeds the configured limit.")
            if normalized:
                result.append(ParsedBlock(index=len(result), text=normalized))
        return tuple(result)

    def _parse_pdf(self, data: bytes) -> ParsedDocument:
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise DocumentParsingError("Password-protected PDF documents are not supported.")
            if len(reader.pages) > self._max_pdf_pages:
                raise DocumentParsingError("PDF exceeds the configured page limit.")
            blocks = self._bounded([(page.extract_text() or "") for page in reader.pages])
        except DocumentParsingError:
            raise
        except Exception as error:
            raise DocumentParsingError("PDF could not be parsed safely.") from error
        if not blocks:
            raise RequiresOCRError("PDF contains no extractable text.")
        return ParsedDocument(blocks, "pypdf", "6", len(reader.pages))

    def _parse_docx(self, data: bytes) -> ParsedDocument:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
            raise DocumentParsingError("DOCX could not be parsed safely.") from error
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = [
            "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
            for paragraph in root.iter(f"{namespace}p")
        ]
        return ParsedDocument(self._bounded(paragraphs), "docx-xml", "1")

    def _parse_txt(self, data: bytes) -> ParsedDocument:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DocumentParsingError("Text document encoding is not supported.") from error
        return ParsedDocument(self._bounded(text.splitlines()), "utf8-text", "1")
