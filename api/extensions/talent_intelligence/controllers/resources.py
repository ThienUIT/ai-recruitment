"""Thin Flask-RESTX resources for Talent Intelligence Phase 1."""

from collections.abc import Callable
from uuid import uuid4

from flask import request
from flask_restx import Namespace, Resource
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from controllers.common.schema import (
    query_params_from_model,
    query_params_from_request,
    register_response_schema_models,
    register_schema_models,
)
from extensions.ext_database import db
from libs.helper import dump_response
from libs.login import current_account_with_tenant, login_required

from ..audit import AuditService
from ..errors import TalentIntelligenceError, ValidationError
from ..permissions import TalentAction, require_permission
from ..schemas.domain import (
    AuditEventListResponse,
    AuditVerificationResponse,
    CandidateCreatePayload,
    CandidateListResponse,
    CandidateProfilePayload,
    CandidateProfileResponse,
    CandidateResponse,
    CandidateUpdatePayload,
    JobCreatePayload,
    JobListResponse,
    JobResponse,
    JobUpdatePayload,
    PaginationQuery,
    ScoringPolicyCreatePayload,
    ScoringPolicyListResponse,
    ScoringPolicyResponse,
)
from ..services import CandidateProfileService, CandidateService, JobService, ScoringPolicyService


def _correlation_id() -> str:
    return request.headers.get("X-Correlation-ID") or str(uuid4())


def _context(action: TalentAction):
    account, tenant_id = current_account_with_tenant()
    require_permission(account, action)
    return account, tenant_id


def _validate_payload[ModelT: BaseModel](model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate(request.get_json(silent=True) or {})
    except PydanticValidationError as error:
        raise ValidationError("Request validation failed.") from error


def _validate_query[ModelT: BaseModel](model: type[ModelT]) -> ModelT:
    try:
        return query_params_from_request(model)
    except PydanticValidationError as error:
        raise ValidationError("Query validation failed.") from error


def register_error_handlers(namespace: Namespace) -> None:
    """Translate extension and Pydantic errors without leaking stack details."""

    @namespace.errorhandler(TalentIntelligenceError)
    def handle_domain_error(error: TalentIntelligenceError):
        return {"message": error.description}, error.status_code

    @namespace.errorhandler(PydanticValidationError)
    def handle_validation_error(error: PydanticValidationError):
        return {"message": "Request validation failed.", "errors": error.errors(include_input=False)}, 400


def register_domain_routes(namespace: Namespace) -> None:
    """Register all Phase 1 resources on Dify's console namespace."""

    request_models = (
        CandidateCreatePayload,
        CandidateProfilePayload,
        CandidateUpdatePayload,
        JobCreatePayload,
        JobUpdatePayload,
        PaginationQuery,
        ScoringPolicyCreatePayload,
    )
    response_models = (
        AuditEventListResponse,
        AuditVerificationResponse,
        CandidateListResponse,
        CandidateProfileResponse,
        CandidateResponse,
        JobListResponse,
        JobResponse,
        ScoringPolicyListResponse,
        ScoringPolicyResponse,
    )
    register_schema_models(namespace, *request_models)
    register_response_schema_models(namespace, *response_models)

    def expect(model: type) -> Callable:
        return namespace.expect(namespace.models[model.__name__])

    @namespace.route("/talent-intelligence/candidates")
    class CandidateCollectionApi(Resource):
        @login_required
        @expect(CandidateCreatePayload)
        @namespace.response(201, "Created", namespace.models[CandidateResponse.__name__])
        def post(self):
            account, tenant_id = _context(TalentAction.MANAGE_CANDIDATE)
            payload = _validate_payload(CandidateCreatePayload)
            with Session(db.engine, expire_on_commit=False) as session:
                candidate = CandidateService(session).create(tenant_id, account, payload, _correlation_id())
                return dump_response(CandidateResponse, candidate), 201

        @login_required
        @namespace.doc(params=query_params_from_model(PaginationQuery))
        @namespace.response(200, "Success", namespace.models[CandidateListResponse.__name__])
        def get(self):
            _, tenant_id = _context(TalentAction.READ_CANDIDATE)
            query = _validate_query(PaginationQuery)
            with Session(db.engine, expire_on_commit=False) as session:
                candidates, total = CandidateService(session).list(tenant_id, page=query.page, limit=query.limit)
                return dump_response(
                    CandidateListResponse,
                    {"data": candidates, "page": query.page, "limit": query.limit, "total": total},
                )

    @namespace.route("/talent-intelligence/candidates/<string:candidate_id>")
    class CandidateDetailApi(Resource):
        @login_required
        @namespace.response(200, "Success", namespace.models[CandidateResponse.__name__])
        def get(self, candidate_id: str):
            _, tenant_id = _context(TalentAction.READ_CANDIDATE)
            with Session(db.engine, expire_on_commit=False) as session:
                return dump_response(CandidateResponse, CandidateService(session).get(tenant_id, candidate_id))

        @login_required
        @expect(CandidateUpdatePayload)
        @namespace.response(200, "Success", namespace.models[CandidateResponse.__name__])
        def patch(self, candidate_id: str):
            account, tenant_id = _context(TalentAction.MANAGE_CANDIDATE)
            payload = _validate_payload(CandidateUpdatePayload)
            with Session(db.engine, expire_on_commit=False) as session:
                candidate = CandidateService(session).update(
                    tenant_id, account, candidate_id, payload, _correlation_id()
                )
                return dump_response(CandidateResponse, candidate)

    @namespace.route("/talent-intelligence/candidates/<string:candidate_id>/request-deletion")
    class CandidateDeletionApi(Resource):
        @login_required
        @namespace.response(200, "Success", namespace.models[CandidateResponse.__name__])
        def post(self, candidate_id: str):
            account, tenant_id = _context(TalentAction.REQUEST_CANDIDATE_DELETION)
            with Session(db.engine, expire_on_commit=False) as session:
                candidate = CandidateService(session).request_deletion(
                    tenant_id, account, candidate_id, _correlation_id()
                )
                return dump_response(CandidateResponse, candidate)

    @namespace.route("/talent-intelligence/candidates/<string:candidate_id>/profile")
    class CandidateProfileApi(Resource):
        @login_required
        @expect(CandidateProfilePayload)
        @namespace.response(200, "Success", namespace.models[CandidateProfileResponse.__name__])
        def put(self, candidate_id: str):
            _, tenant_id = _context(TalentAction.MANAGE_CANDIDATE)
            payload = _validate_payload(CandidateProfilePayload)
            with Session(db.engine, expire_on_commit=False) as session:
                profile = CandidateProfileService(session).put(tenant_id, candidate_id, payload)
                return dump_response(CandidateProfileResponse, profile)

        @login_required
        @namespace.response(200, "Success", namespace.models[CandidateProfileResponse.__name__])
        def get(self, candidate_id: str):
            _, tenant_id = _context(TalentAction.READ_CANDIDATE)
            with Session(db.engine, expire_on_commit=False) as session:
                profile = CandidateProfileService(session).get(tenant_id, candidate_id)
                return dump_response(CandidateProfileResponse, profile)

    @namespace.route("/talent-intelligence/jobs")
    class JobCollectionApi(Resource):
        @login_required
        @expect(JobCreatePayload)
        @namespace.response(201, "Created", namespace.models[JobResponse.__name__])
        def post(self):
            account, tenant_id = _context(TalentAction.MANAGE_JOB)
            payload = _validate_payload(JobCreatePayload)
            with Session(db.engine, expire_on_commit=False) as session:
                job = JobService(session).create(tenant_id, account, payload, _correlation_id())
                return dump_response(JobResponse, job), 201

        @login_required
        @namespace.doc(params=query_params_from_model(PaginationQuery))
        @namespace.response(200, "Success", namespace.models[JobListResponse.__name__])
        def get(self):
            _, tenant_id = _context(TalentAction.READ_JOB)
            query = _validate_query(PaginationQuery)
            with Session(db.engine, expire_on_commit=False) as session:
                jobs, total = JobService(session).list(tenant_id, page=query.page, limit=query.limit)
                return dump_response(
                    JobListResponse,
                    {"data": jobs, "page": query.page, "limit": query.limit, "total": total},
                )

    @namespace.route("/talent-intelligence/jobs/<string:job_id>")
    class JobDetailApi(Resource):
        @login_required
        @namespace.response(200, "Success", namespace.models[JobResponse.__name__])
        def get(self, job_id: str):
            _, tenant_id = _context(TalentAction.READ_JOB)
            with Session(db.engine, expire_on_commit=False) as session:
                return dump_response(JobResponse, JobService(session).get(tenant_id, job_id))

        @login_required
        @expect(JobUpdatePayload)
        @namespace.response(200, "Success", namespace.models[JobResponse.__name__])
        def patch(self, job_id: str):
            account, tenant_id = _context(TalentAction.MANAGE_JOB)
            payload = _validate_payload(JobUpdatePayload)
            with Session(db.engine, expire_on_commit=False) as session:
                job = JobService(session).update(tenant_id, account, job_id, payload, _correlation_id())
                return dump_response(JobResponse, job)

    @namespace.route("/talent-intelligence/jobs/<string:job_id>/publish")
    class JobPublishApi(Resource):
        @login_required
        @namespace.response(200, "Success", namespace.models[JobResponse.__name__])
        def post(self, job_id: str):
            account, tenant_id = _context(TalentAction.MANAGE_JOB)
            with Session(db.engine, expire_on_commit=False) as session:
                job = JobService(session).publish(tenant_id, account, job_id, _correlation_id())
                return dump_response(JobResponse, job)

    @namespace.route("/talent-intelligence/scoring-policies")
    class ScoringPolicyCollectionApi(Resource):
        @login_required
        @expect(ScoringPolicyCreatePayload)
        @namespace.response(201, "Created", namespace.models[ScoringPolicyResponse.__name__])
        def post(self):
            account, tenant_id = _context(TalentAction.MANAGE_SCORING_POLICY)
            payload = _validate_payload(ScoringPolicyCreatePayload)
            with Session(db.engine, expire_on_commit=False) as session:
                policy = ScoringPolicyService(session).create(tenant_id, account, payload, _correlation_id())
                return dump_response(ScoringPolicyResponse, policy), 201

        @login_required
        @namespace.doc(params=query_params_from_model(PaginationQuery))
        @namespace.response(200, "Success", namespace.models[ScoringPolicyListResponse.__name__])
        def get(self):
            _, tenant_id = _context(TalentAction.MANAGE_SCORING_POLICY)
            query = _validate_query(PaginationQuery)
            with Session(db.engine, expire_on_commit=False) as session:
                policies, total = ScoringPolicyService(session).list(tenant_id, page=query.page, limit=query.limit)
                return dump_response(
                    ScoringPolicyListResponse,
                    {"data": policies, "page": query.page, "limit": query.limit, "total": total},
                )

    @namespace.route("/talent-intelligence/scoring-policies/<string:policy_id>")
    class ScoringPolicyDetailApi(Resource):
        @login_required
        @namespace.response(200, "Success", namespace.models[ScoringPolicyResponse.__name__])
        def get(self, policy_id: str):
            _, tenant_id = _context(TalentAction.MANAGE_SCORING_POLICY)
            with Session(db.engine, expire_on_commit=False) as session:
                return dump_response(ScoringPolicyResponse, ScoringPolicyService(session).get(tenant_id, policy_id))

    @namespace.route("/talent-intelligence/scoring-policies/<string:policy_id>/activate")
    class ScoringPolicyActivateApi(Resource):
        @login_required
        @namespace.response(200, "Success", namespace.models[ScoringPolicyResponse.__name__])
        def post(self, policy_id: str):
            account, tenant_id = _context(TalentAction.MANAGE_SCORING_POLICY)
            with Session(db.engine, expire_on_commit=False) as session:
                policy = ScoringPolicyService(session).activate(tenant_id, account, policy_id, _correlation_id())
                return dump_response(ScoringPolicyResponse, policy)

    @namespace.route("/talent-intelligence/audit")
    class AuditCollectionApi(Resource):
        @login_required
        @namespace.doc(params=query_params_from_model(PaginationQuery))
        @namespace.response(200, "Success", namespace.models[AuditEventListResponse.__name__])
        def get(self):
            _, tenant_id = _context(TalentAction.READ_AUDIT)
            query = _validate_query(PaginationQuery)
            with Session(db.engine, expire_on_commit=False) as session:
                events, total = AuditService(session).list_events(tenant_id, page=query.page, limit=query.limit)
                return dump_response(
                    AuditEventListResponse,
                    {"data": events, "page": query.page, "limit": query.limit, "total": total},
                )

    @namespace.route("/talent-intelligence/audit/verify")
    class AuditVerificationApi(Resource):
        @login_required
        @namespace.response(200, "Success", namespace.models[AuditVerificationResponse.__name__])
        def get(self):
            _, tenant_id = _context(TalentAction.READ_AUDIT)
            with Session(db.engine, expire_on_commit=False) as session:
                return dump_response(AuditVerificationResponse, AuditService(session).verify_chain(tenant_id))
