# Local document parsing

PDF parsing uses pypdf strict mode with password rejection and a page limit. A PDF with no extractable text becomes `requires_ocr`; Phase 2 deliberately implements no OCR. DOCX reads only `word/document.xml` after safe ZIP validation. TXT accepts UTF-8/UTF-8 BOM and rejects binary input. All formats share an extracted-character limit.

Parsers return ordered in-memory blocks. Raw extracted text is never written to CandidateProfile, logs, audit metadata, or database columns.
