"""Identifier-only Celery entry points for secure document processing."""

from uuid import uuid4

from celery import shared_task
from sqlalchemy.orm import Session

from extensions.ext_database import db

from .services import CandidateDeletionService, CandidateDocumentProcessor, RawRetentionService


@shared_task(queue="retention", bind=True, max_retries=3, default_retry_delay=30)
def process_candidate_document(self, tenant_id: str, document_id: str, correlation_id: str) -> None:
    try:
        with Session(db.engine, expire_on_commit=False) as session:
            CandidateDocumentProcessor(session).process(tenant_id, document_id, correlation_id)
    # Celery receives a sanitized retry error so storage/parser details cannot reach logs.
    except Exception:
        raise self.retry(exc=RuntimeError("Secure document processing retry requested.")) from None


@shared_task(queue="retention", bind=True, max_retries=3, default_retry_delay=60)
def execute_candidate_deletion(self, tenant_id: str, candidate_id: str, correlation_id: str) -> None:
    try:
        with Session(db.engine, expire_on_commit=False) as session:
            CandidateDeletionService(session).execute(tenant_id, candidate_id, correlation_id)
    # Celery receives a sanitized retry error so storage details cannot reach logs.
    except Exception:
        raise self.retry(exc=RuntimeError("Candidate deletion retry requested.")) from None


@shared_task(name="talent_intelligence.delete_expired_raw", queue="retention")
def delete_expired_raw_documents() -> int:
    with Session(db.engine, expire_on_commit=False) as session:
        return RawRetentionService(session).delete_expired(str(uuid4()))
