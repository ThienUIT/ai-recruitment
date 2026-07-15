# Secure CV ingestion

Phase 2 accepts authenticated multipart PDF, DOCX, and UTF-8 TXT uploads. It validates bounded size, MIME, signature, archive expansion, and SHA-256 before private quarantine storage. Original filenames are discarded.

```mermaid
flowchart LR
  A[Authenticated stream] --> B[Bounded validation]
  B --> C[Private quarantine]
  C --> D[ClamAV]
  D -->|clean| E[Local parser]
  D -->|infected| X[Verified deletion]
  E --> F[Local PII recognition]
  F --> G[Stable masking]
  G --> H[Independent leak gate]
  H -->|safe| I[Encrypted PII and masked artifact]
  H -->|leak| J[Review; downstream blocked]
```

Celery receives tenant, document, and correlation identifiers only. Raw bytes and extracted text are never task arguments or database columns.
