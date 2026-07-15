"""Map Talent Intelligence actions to Dify's existing workspace permissions."""

import enum

from models import Account

from ..errors import PermissionDeniedError


class TalentAction(enum.StrEnum):
    READ_CANDIDATE = "read_candidate"
    MANAGE_CANDIDATE = "manage_candidate"
    REQUEST_CANDIDATE_DELETION = "request_candidate_deletion"
    READ_JOB = "read_job"
    MANAGE_JOB = "manage_job"
    MANAGE_SCORING_POLICY = "manage_scoring_policy"
    READ_AUDIT = "read_audit"


_READ_ACTIONS = {TalentAction.READ_CANDIDATE, TalentAction.READ_JOB}
_EDITOR_ACTIONS = {
    TalentAction.MANAGE_CANDIDATE,
    TalentAction.REQUEST_CANDIDATE_DELETION,
    TalentAction.MANAGE_JOB,
}
_ADMIN_ACTIONS = {TalentAction.MANAGE_SCORING_POLICY, TalentAction.READ_AUDIT}


def require_permission(account: Account, action: TalentAction) -> None:
    """Authorize an action using Dify's current workspace role properties."""

    if action in _READ_ACTIONS:
        return
    if action in _EDITOR_ACTIONS and account.has_edit_permission:
        return
    if action in _ADMIN_ACTIONS and account.is_admin_or_owner:
        return
    raise PermissionDeniedError(f"Workspace role is not permitted to {action.value}.")
