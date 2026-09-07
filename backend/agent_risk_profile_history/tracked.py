from backend.agent_risk_profile import ACTIVE, LLMAgentRiskProfileService
from backend.agent_risk_profile_activation import ACTIVATED as ACTIVATION_ACTIVATED
from backend.agent_risk_profile_activation import LLMAgentRiskProfileActivationService

from .models import ACTIVATED, ARCHIVED, CREATED, DEACTIVATED, UPDATED
from .service import LLMAgentRiskProfileHistoryService

# Fields save() always changes regardless of whether anything a caller
# actually asked to change did -- comparing raw to_dict() snapshots
# without excluding these would make every update()/archive() call look
# "meaningful" even when it truly changed nothing (the exact same
# reasoning backend.agent_policy_history.tracked already documents for
# its own analogous wrapper).
_VOLATILE_FIELDS = ("updated_at",)


def _without_volatile_fields(snapshot: dict) -> dict:
    return {key: value for key, value in snapshot.items() if key not in _VOLATILE_FIELDS}


def _meaningfully_different(before: dict, after: dict) -> bool:
    if before is None or after is None:
        return before != after
    return _without_volatile_fields(before) != _without_volatile_fields(after)


class LLMAgentRiskProfileHistoryTrackedService(LLMAgentRiskProfileService):
    """Commit #1's LLMAgentRiskProfileService, unchanged, with exactly
    one more step after create()/update()/archive() succeeds: recording
    a LLMAgentRiskProfileChange for it.

    Not a second profile service, and Commit #1 is never modified:
    every method here delegates the entire operation to
    super().create()/update()/archive() first, completely unchanged, and
    only afterward records what happened. A read (get()/list()/resolve())
    is never wrapped, since nothing about a read is ever a change to
    track (Rule: "Historical reads must not alter current state").

    Recording is best-effort: a failure in the history store can never
    surface to the caller or undo an already-applied profile change --
    "do not alter current profile behavior" holds by construction, since
    the real create()/update()/archive() call has already fully
    completed, successfully, by the time any history code runs.

    update()/archive() only record when the resulting snapshot actually
    differs from the one immediately before it (excluding the
    always-changing updated_at) -- an idempotent archive() of an
    already-ARCHIVED profile, or an update() that changed nothing,
    produces no new history entry, per "track *meaningful* changes".
    create() always records: a brand-new profile is inherently a
    meaningful change.
    """

    def __init__(self, store=None, history_service: LLMAgentRiskProfileHistoryService = None, actor: str = None):
        super().__init__(store)
        self._history_service = history_service if history_service is not None else LLMAgentRiskProfileHistoryService()
        self._actor = actor

    def _safe_record(self, scope_id, profile_id, change_type, version, before, after) -> None:
        try:
            self._history_service.record_change(
                scope_id, profile_id, change_type, version, before, after, actor=self._actor
            )
        except Exception:
            pass

    def create(
        self, scope_id, name, action_rules=None, default_level=None, status=ACTIVE, action_name=None,
        action_category=None,
    ):
        profile = super().create(scope_id, name, action_rules, default_level, status, action_name, action_category)
        self._safe_record(profile.scope_id, profile.profile_id, CREATED, profile.version, before=None, after=profile.to_dict())
        return profile

    def update(self, profile_id, name=None, action_rules=None, default_level=None):
        before = self.get(profile_id).to_dict()
        profile = super().update(profile_id, name=name, action_rules=action_rules, default_level=default_level)
        after = profile.to_dict()
        if _meaningfully_different(before, after):
            self._safe_record(profile.scope_id, profile_id, UPDATED, profile.version, before=before, after=after)
        return profile

    def archive(self, profile_id):
        before = self.get(profile_id).to_dict()
        profile = super().archive(profile_id)
        after = profile.to_dict()
        if _meaningfully_different(before, after):
            self._safe_record(profile.scope_id, profile_id, ARCHIVED, profile.version, before=before, after=after)
        return profile


class LLMAgentRiskProfileActivationHistoryTrackedService(LLMAgentRiskProfileActivationService):
    """Commit #6's LLMAgentRiskProfileActivationService, unchanged, with
    exactly one more step after activate()/deactivate() succeeds:
    recording a LLMAgentRiskProfileChange for it, the same "delegate
    first, then record, best-effort" shape
    LLMAgentRiskProfileHistoryTrackedService already uses for Commit #1.

    Composes safely alongside LLMAgentRiskProfileHistoryTrackedService:
    if this class's own profile_service happens to be that tracked
    service, deactivate()'s internal archive() call already records its
    own generic ARCHIVED entry -- this class's own DEACTIVATED entry is
    a second, semantically distinct record ("this was a deliberate
    deactivation via the activation service", not merely "the profile
    is now archived"), not a duplicate of the same fact, the same way
    backend.agent_policy_history's own two tracked wrappers (for Commit
    #1 policies and Commit #5 exceptions) are already designed to
    compose independently over the same history_service without
    conflicting.

    activate() only records when Commit #6's own ActivationResult.status
    says something actually changed (ACTIVATED, not ALREADY_ACTIVE) --
    reusing that service's own already-computed "did anything actually
    change" signal rather than re-deriving one from a before/after
    comparison a second time. deactivate() records only when the
    resulting snapshot actually differs from the one immediately before
    it, mirroring LLMAgentRiskProfileHistoryTrackedService's own
    archive() gating exactly (an idempotent re-deactivation of an
    already-ARCHIVED profile produces no new entry).
    """

    def __init__(
        self,
        profile_service,
        version_service,
        compatibility=None,
        history_service: LLMAgentRiskProfileHistoryService = None,
        actor: str = None,
    ):
        super().__init__(profile_service, version_service, compatibility)
        self._history_service = history_service if history_service is not None else LLMAgentRiskProfileHistoryService()
        self._actor = actor

    def _safe_record(self, scope_id, profile_id, change_type, version, before, after, reason=None) -> None:
        try:
            self._history_service.record_change(
                scope_id, profile_id, change_type, version, before, after, actor=self._actor, reason=reason
            )
        except Exception:
            pass

    def activate(self, profile_id, version, scope_id, target_context=None, actor=None, reason=None):
        before = self._profile_service.get(profile_id).to_dict()
        result = super().activate(profile_id, version, scope_id, target_context=target_context, actor=actor, reason=reason)
        if result.status == ACTIVATION_ACTIVATED:
            after = self._profile_service.get(profile_id).to_dict()
            self._safe_record(
                scope_id, profile_id, ACTIVATED, result.version, before=before, after=after,
                reason=reason if reason is not None else f"activated version {version}",
            )
        return result

    def deactivate(self, profile_id, scope_id):
        before = self._profile_service.get(profile_id).to_dict()
        profile = super().deactivate(profile_id, scope_id)
        after = profile.to_dict()
        if _meaningfully_different(before, after):
            self._safe_record(profile.scope_id, profile_id, DEACTIVATED, profile.version, before=before, after=after)
        return profile
