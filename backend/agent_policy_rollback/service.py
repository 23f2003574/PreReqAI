from backend.agent_policy_engine import (
    ArchivedPolicyError,
    DuplicateRuleIdError,
    InvalidAgentPolicyError,
    InvalidPolicyRuleError,
    UnknownAgentPolicyError,
)
from backend.agent_policy_versioning import LLMAgentPolicyVersionService, UnknownPolicyVersionError


class LLMAgentPolicyRollbackError(ValueError):
    """Raised when rollback() cannot be carried out safely -- an unknown
    policy or target version, or a target version that no longer passes
    Commit #1's own rule validation (e.g. the policy has since been
    archived). Chains the real underlying error as __cause__, so a
    caller who wants the specific reason can still find it."""


class LLMAgentPolicyRollbackService:
    """Safely restores a Commit #1 policy's rules to a previously
    recorded Commit #11 version, without rewinding or mutating any
    history -- the same "load target, validate, append a new record,
    leave everything before it untouched" shape this repository's own
    ...RollbackService already establishes elsewhere (e.g. for consumer
    projection binding deployments): a rollback is recorded as a new,
    append-only version; no prior version is ever modified or removed,
    and the most recently appended version is always the policy's
    current one.

    Built entirely on Commit #11's own methods, never a second
    versioning or validation path:

        1. "Load the target immutable version"  -> get_version()
        2. "Validate it using the existing policy validator" ->
           create_version()'s own delegation to Commit #1's
           LLMAgentPolicyService.update(), which already runs the exact
           rule validation every other update goes through
        3. "Create a new current version containing that configuration"
           -> create_version()'s own update() + version computation
        4. "Record the rollback/change provenance" -> create_version()'s
           own record_change() call, with reason forwarded verbatim and
           actor as created_by
        5. "Leave all previous versions untouched" -> automatic:
           list_versions()/get_version() are pure reads recomputed from
           Commit #10's own append-only trail, which rollback() never
           mutates -- there is nothing to leave untouched by discipline
           other than by never having a way to touch it in the first
           place

    Idempotent by construction, not by a special case: rolling back to
    the version that is already current calls create_version() with
    that version's own (unchanged) rules, which Commit #11's own
    before/after rules comparison recognizes as no meaningful change --
    no duplicate version is created, and the already-current version is
    returned unchanged. Rolling back to the same target twice in a row
    behaves the same way the second time.
    """

    def __init__(self, version_service: LLMAgentPolicyVersionService):
        self._version_service = version_service

    def rollback(self, policy_id: str, target_version: int, reason: str, actor: str = None):
        """Restore policy_id's current rules to those of `target_version`.

        Returns the resulting current LLMAgentPolicyVersion -- a newly
        appended one if the target's rules actually differ from what is
        current now, or the already-current version unchanged otherwise
        (see class docstring: "idempotent by construction").

        Raises:
            LLMAgentPolicyRollbackError: If policy_id or target_version
                is unknown, or the target version's rules no longer pass
                Commit #1's own validation (e.g. the policy is archived)
        """
        if not reason or not isinstance(reason, str):
            raise LLMAgentPolicyRollbackError("reason is required to roll back a policy")

        try:
            target = self._version_service.get_version(policy_id, target_version)
        except UnknownPolicyVersionError as error:
            raise LLMAgentPolicyRollbackError(
                f"cannot roll back policy {policy_id!r}: version {target_version} does not exist"
            ) from error

        try:
            return self._version_service.create_version(
                policy_id,
                target.rules,
                created_by=actor,
                reason=f"rollback to version {target_version}: {reason}",
            )
        except UnknownAgentPolicyError as error:
            raise LLMAgentPolicyRollbackError(f"cannot roll back policy {policy_id!r}: policy is unknown") from error
        except ArchivedPolicyError as error:
            raise LLMAgentPolicyRollbackError(
                f"cannot roll back policy {policy_id!r}: policy is archived and cannot be updated"
            ) from error
        except (InvalidAgentPolicyError, InvalidPolicyRuleError, DuplicateRuleIdError) as error:
            raise LLMAgentPolicyRollbackError(
                f"cannot roll back policy {policy_id!r} to version {target_version}: "
                f"target version failed validation ({error})"
            ) from error
