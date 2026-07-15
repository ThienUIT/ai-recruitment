"""Domain errors compatible with Dify's shared HTTP error handling."""

from werkzeug.exceptions import HTTPException


class TalentIntelligenceError(HTTPException):
    status_code = 400
    code = 400

    def __init__(self, description: str, *, code: str | None = None) -> None:
        super().__init__(description=description)
        self.error_code = code


class NotFoundError(TalentIntelligenceError):
    status_code = 404
    code = 404


class PermissionDeniedError(TalentIntelligenceError):
    status_code = 403
    code = 403


class ConflictError(TalentIntelligenceError):
    status_code = 409
    code = 409


class ValidationError(TalentIntelligenceError):
    status_code = 400


class PayloadTooLargeError(TalentIntelligenceError):
    status_code = 413
    code = 413


class UnsupportedMediaTypeError(TalentIntelligenceError):
    status_code = 415
    code = 415
