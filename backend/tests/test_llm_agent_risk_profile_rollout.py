import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import LLMAgentRiskProfileService, RiskProfileActionRule
from backend.agent_risk_profile_activation import (
    IncompatibleRiskProfileVersionError,
    LLMAgentRiskProfileActivationService,
)
from backend.agent_risk_profile_approval import LLMAgentRiskProfileApprovalService
from backend.agent_risk_profile_history import (
    ACTIVATED,
    LLMAgentRiskProfileActivationHistoryTrackedService,
    LLMAgentRiskProfileHistoryService,
)
from backend.agent_risk_profile_rollout import (
    COMPLETED,
    FAILED,
    IN_PROGRESS,
    PAUSED,
    STANDARD,
    ConflictingRolloutError,
    IncompleteRolloutError,
    InvalidRolloutStrategyError,
    InvalidRolloutTransitionError,
    LLMAgentRiskProfileRolloutService,
    RiskProfileRollout,
    RolloutRequiresApprovalError,
    UnknownRolloutError,
)
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


def _services(activation_service=None):
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    activation_service = activation_service or LLMAgentRiskProfileActivationService(profile_service, version_service)
    approval_service = LLMAgentRiskProfileApprovalService(profile_service, version_service)
    rollout_service = LLMAgentRiskProfileRolloutService(
        profile_service, version_service, activation_service, approval_service
    )
    return profile_service, version_service, activation_service, approval_service, rollout_service


def _approve(profile_service, version_service, approval_service, profile_id, version, scope_id):
    approval = approval_service.request_approval(profile_id, version, scope_id, requested_by="alice")
    return approval_service.approve(approval.approval_id, "reviewer-1")


# --- unapproved versions cannot start ------------------------------------


def test_unapproved_version_cannot_start_rollout():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)

    with pytest.raises(RolloutRequiresApprovalError):
        rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)


def test_rejected_version_cannot_start_rollout():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    approval = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    approval_service.reject(approval.approval_id, "reviewer-1", "not ready")

    with pytest.raises(RolloutRequiresApprovalError):
        rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)


# --- invalid/incompatible versions cannot start ---------------------------


def test_incompatible_version_cannot_start_rollout_even_if_approved():
    from dataclasses import replace

    from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility

    class _AlwaysIncompatible(LLMAgentRiskProfileCompatibility):
        def check(self, profile, target_context):
            result = super().check(profile, target_context)
            return replace(result, compatible=False, reasons=["forced incompatible"])

    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    activation_service = LLMAgentRiskProfileActivationService(profile_service, version_service)
    approval_service = LLMAgentRiskProfileApprovalService(profile_service, version_service)

    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    # Approve while compatibility is still real, then swap in a forced-
    # incompatible checker for the rollout service itself, simulating
    # something having changed in the runtime since approval was granted.
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")

    rollout_service = LLMAgentRiskProfileRolloutService(
        profile_service, version_service, activation_service, approval_service,
        compatibility=_AlwaysIncompatible(),
    )

    with pytest.raises(IncompatibleRiskProfileVersionError):
        rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)


def test_invalid_strategy_rejected():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")

    with pytest.raises(InvalidRolloutStrategyError):
        rollout_service.start_rollout(profile.profile_id, 1, "scope-1", "canary")


# --- deterministic stage order --------------------------------------------


def test_rollout_progresses_through_stages_in_deterministic_order():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")

    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    assert isinstance(rollout, RiskProfileRollout)
    assert rollout.state == IN_PROGRESS
    assert rollout.current_stage is None
    assert rollout.stages == ("pre_flight", "activate", "verify")

    after_1 = rollout_service.advance_rollout(rollout.rollout_id)
    assert after_1.current_stage == "pre_flight"
    assert after_1.state == IN_PROGRESS

    after_2 = rollout_service.advance_rollout(rollout.rollout_id)
    assert after_2.current_stage == "activate"

    after_3 = rollout_service.advance_rollout(rollout.rollout_id)
    assert after_3.current_stage == "verify"

    completed = rollout_service.complete_rollout(rollout.rollout_id)
    assert completed.state == COMPLETED
    assert completed.completed_at is not None

    live = profile_service.get(profile.profile_id)
    assert live.action_rules[0].rule_id == "r1"


def test_advance_never_skips_a_stage():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)

    seen_stages = []
    rid = rollout.rollout_id
    for _ in range(len(rollout.stages)):
        rollout = rollout_service.advance_rollout(rid)
        seen_stages.append(rollout.current_stage)

    assert seen_stages == list(rollout.stages)


def test_advance_past_last_stage_raises():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)

    for _ in range(3):
        rollout = rollout_service.advance_rollout(rollout.rollout_id)

    with pytest.raises(InvalidRolloutTransitionError):
        rollout_service.advance_rollout(rollout.rollout_id)


# --- pause/resume preserves state ------------------------------------


def test_pause_preserves_current_stage_and_resumes_via_advance():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    rollout = rollout_service.advance_rollout(rollout.rollout_id)  # pre_flight

    paused = rollout_service.pause_rollout(rollout.rollout_id)
    assert paused.state == PAUSED
    assert paused.current_stage == "pre_flight"
    assert paused.stages == rollout.stages

    resumed = rollout_service.advance_rollout(paused.rollout_id)
    assert resumed.state == IN_PROGRESS
    assert resumed.current_stage == "activate"


def test_pause_is_idempotent():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)

    once = rollout_service.pause_rollout(rollout.rollout_id)
    twice = rollout_service.pause_rollout(rollout.rollout_id)
    assert once.state == PAUSED
    assert twice.state == PAUSED


def test_cannot_pause_a_completed_or_failed_rollout():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    for _ in range(3):
        rollout = rollout_service.advance_rollout(rollout.rollout_id)
    rollout_service.complete_rollout(rollout.rollout_id)

    with pytest.raises(InvalidRolloutTransitionError):
        rollout_service.pause_rollout(rollout.rollout_id)


# --- failed stages preserve the previously active profile -----------------


def test_failed_stage_preserves_previously_active_profile():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1, live: LOW
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2, live: HIGH
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")

    before = profile_service.get(profile.profile_id)
    assert before.default_level == LEVEL_HIGH

    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    rollout = rollout_service.advance_rollout(rollout.rollout_id)  # pre_flight succeeds

    # Archive the profile out from under the rollout so the "activate"
    # stage's own real activate() call genuinely fails.
    profile_service.archive(profile.profile_id)
    failed = rollout_service.advance_rollout(rollout.rollout_id)  # activate -- fails

    assert failed.state == FAILED
    assert failed.current_stage == "pre_flight"  # never advanced past the last real success
    assert failed.provenance["failed_stage"] == "activate"

    # Confirm the live content is still exactly whatever v2 last set it
    # to, never touched by the failed activate() attempt.
    live = profile_service.get(profile.profile_id)
    assert live.default_level == LEVEL_HIGH


def test_cannot_advance_a_failed_rollout_further():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    rollout = rollout_service.advance_rollout(rollout.rollout_id)

    profile_service.archive(profile.profile_id)
    failed = rollout_service.advance_rollout(rollout.rollout_id)
    assert failed.state == FAILED

    with pytest.raises(InvalidRolloutTransitionError):
        rollout_service.advance_rollout(failed.rollout_id)


# --- completion requires all stages to succeed ----------------------------


def test_complete_before_all_stages_succeed_raises():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)

    with pytest.raises(IncompleteRolloutError):
        rollout_service.complete_rollout(rollout.rollout_id)

    rollout = rollout_service.advance_rollout(rollout.rollout_id)
    with pytest.raises(IncompleteRolloutError):
        rollout_service.complete_rollout(rollout.rollout_id)


def test_complete_a_paused_rollout_raises():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    for _ in range(3):
        rollout = rollout_service.advance_rollout(rollout.rollout_id)
    rollout_service.pause_rollout(rollout.rollout_id)

    with pytest.raises(InvalidRolloutTransitionError):
        rollout_service.complete_rollout(rollout.rollout_id)


# --- conflicting concurrent rollouts rejected ------------------------------


def test_conflicting_concurrent_rollout_rejected():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    _approve(profile_service, version_service, approval_service, profile.profile_id, 2, "scope-1")

    rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)

    with pytest.raises(ConflictingRolloutError):
        rollout_service.start_rollout(profile.profile_id, 2, "scope-1", STANDARD)


def test_new_rollout_allowed_after_prior_one_completed():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    _approve(profile_service, version_service, approval_service, profile.profile_id, 2, "scope-1")

    first = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    for _ in range(3):
        first = rollout_service.advance_rollout(first.rollout_id)
    rollout_service.complete_rollout(first.rollout_id)

    second = rollout_service.start_rollout(profile.profile_id, 2, "scope-1", STANDARD)
    assert second.rollout_id != first.rollout_id
    assert second.state == IN_PROGRESS


def test_rollouts_for_different_scopes_do_not_conflict():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    p1 = profile_service.create("scope-1", "p1")
    version_service.create_version(p1.profile_id)
    _approve(profile_service, version_service, approval_service, p1.profile_id, 1, "scope-1")

    p2 = profile_service.create("scope-2", "p2")
    version_service.create_version(p2.profile_id)
    _approve(profile_service, version_service, approval_service, p2.profile_id, 1, "scope-2")

    rollout_service.start_rollout(p1.profile_id, 1, "scope-1", STANDARD)
    rollout2 = rollout_service.start_rollout(p2.profile_id, 1, "scope-2", STANDARD)
    assert rollout2.state == IN_PROGRESS


# --- state transitions persisted correctly --------------------------------


def test_rollout_state_persisted_across_service_calls():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    rollout_service.advance_rollout(rollout.rollout_id)

    fetched = rollout_service.get_rollout(rollout.rollout_id)
    assert fetched.current_stage == "pre_flight"
    assert fetched.state == IN_PROGRESS


def test_unknown_rollout_raises():
    *_, rollout_service = _services()
    with pytest.raises(UnknownRolloutError):
        rollout_service.get_rollout("does-not-exist")
    with pytest.raises(UnknownRolloutError):
        rollout_service.advance_rollout("does-not-exist")


# --- existing activation/history mechanisms are actually reused ----------


def test_activate_stage_reuses_real_activation_service():
    profile_service, version_service, activation_service, approval_service, rollout_service = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")
    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)

    for _ in range(3):
        rollout = rollout_service.advance_rollout(rollout.rollout_id)

    active_profile, active_version = activation_service.get_active("scope-1")
    assert active_profile.profile_id == profile.profile_id
    assert active_version.version == 1


def test_history_infrastructure_is_reused_when_configured():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    tracked_activation = LLMAgentRiskProfileActivationHistoryTrackedService(
        profile_service, version_service, history_service=history_service, actor="rollout-bot"
    )
    approval_service = LLMAgentRiskProfileApprovalService(profile_service, version_service)
    rollout_service = LLMAgentRiskProfileRolloutService(
        profile_service, version_service, tracked_activation, approval_service
    )

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)
    _approve(profile_service, version_service, approval_service, profile.profile_id, 1, "scope-1")

    rollout = rollout_service.start_rollout(profile.profile_id, 1, "scope-1", STANDARD)
    for _ in range(3):
        rollout = rollout_service.advance_rollout(rollout.rollout_id)

    changes = history_service.list(profile.profile_id)
    assert any(change.change_type == ACTIVATED for change in changes)
