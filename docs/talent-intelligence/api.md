# Talent Intelligence Phase 1 API

## Phase 2 document endpoints

- `POST /console/api/talent-intelligence/candidates/{candidate_id}/documents` — editor multipart upload, HTTP 202.
- `GET /console/api/talent-intelligence/candidates/{candidate_id}/documents` — member metadata list.
- `GET .../documents/{document_id}` — member metadata detail.
- `POST .../{document_id}/reprocess` — editor retry, HTTP 202.
- `POST .../{document_id}/delete-raw` — editor verified deletion.
- `POST .../candidates/{candidate_id}/execute-deletion` — admin/owner asynchronous erasure.

Responses exclude original filenames, storage keys, content, ciphertext, and placeholder maps. Cross-tenant identifiers return HTTP 404.

All paths are under `/console/api`, require Dify console authentication, resolve the active tenant, and are absent when `TALENT_INTELLIGENCE_ENABLED=false`.

| Method | Path | Minimum role |
| --- | --- | --- |
| POST, GET | `/talent-intelligence/candidates` | editor to create; member to list |
| GET, PATCH | `/talent-intelligence/candidates/{id}` | member to read; editor to update |
| POST | `/talent-intelligence/candidates/{id}/request-deletion` | editor |
| PUT, GET | `/talent-intelligence/candidates/{id}/profile` | editor to write; member to read |
| POST, GET | `/talent-intelligence/jobs` | editor to create; member to list |
| GET, PATCH | `/talent-intelligence/jobs/{id}` | member to read; editor to update |
| POST | `/talent-intelligence/jobs/{id}/publish` | editor |
| POST, GET | `/talent-intelligence/scoring-policies` | admin/owner |
| GET | `/talent-intelligence/scoring-policies/{id}` | admin/owner |
| POST | `/talent-intelligence/scoring-policies/{id}/activate` | admin/owner |
| GET | `/talent-intelligence/audit` | admin/owner |
| GET | `/talent-intelligence/audit/verify` | admin/owner |

Candidate requests reject unknown fields, including raw CV content. Candidate responses have no CandidatePII fields. CandidateProfile recursively rejects obvious email and Vietnamese phone patterns. This is defense in depth, not complete PII recognition.

Phase 1 implements Candidate create/read/update plus a deletion-request transition, and JobProfile
create/read/update plus a publish transition. It does not claim full CRUD because neither resource exposes a delete
endpoint. CandidatePII is a restricted schema and repository boundary only; production encryption and the encrypted
PII write flow are deferred to Phase 2.

Publishing requires `original_title`, `canonical_title`, `location`, `workplace_mode`, `employment_type`, non-empty `responsibilities`, and non-empty `must_have_skills`. Generic updates cannot publish and published rows reject edits with HTTP 409.

Audit list responses expose `chain_sequence`. Verification returns only validity, event count, the first invalid
event ID, and a non-sensitive failure reason; it never returns audit metadata as a failure diagnostic.

Collection responses follow Dify's direct Pydantic response model and accept `page` (minimum 1) and `limit` (1–100). Validation is HTTP 400, unauthenticated access 401, insufficient role 403, tenant-scoped missing objects 404, and invalid state/uniqueness conflicts 409.
