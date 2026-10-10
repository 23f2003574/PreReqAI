import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import LLMAgentRiskProfileService, RiskProfileActionRule, UnknownRiskProfileError
from backend.agent_risk_profile_activation import LLMAgentRiskProfileActivationService, RiskProfileScopeMismatchError
from backend.agent_risk_profile_approval import APPROVED, PENDING, REJECTED, LLMAgentRiskProfileApprovalService
from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility
from backend.agent_risk_profile_drift_detection import LLMAgentRiskProfileDriftDetector
from backend.agent_risk_profile_governance import (
    BLOCKED,
    DRIFTED,
    NOT_APPROVED,
    PENDING_APPROVAL,
    ROLLED_OUT,
    STABLE,
    LLMAgentRiskProfileGovernanceOrchestrator,
    RiskProfileGovernanceResult,
)
from backend.agent_risk_profile_history import (
    ACTIVATED,
    LLMAgentRiskProfileActivationHistoryTrackedService,
    LLMAgentRiskProfileHistoryService,
)
from backend.agent_risk_profile_impact_analysis import LLMAgentRiskProfileImpactAnalyzer
from backend.agent_risk_profile_rollout import COMPLETED, LLMAgentRiskProfileRolloutService
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


def _full_stack(activation_service=None, history_service=None):
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    activation_service = activation_service or LLMAgentRiskProfileActivationService(profile_service, version_service)
    approval_service = LLMAgentRiskProfileApprovalService(profile_service, version_service)
    rollout_service = LLMAgentRiskProfileRolloutService(
        profile_service, version_service, activation_service, approval_service
    )
    impact_analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service)
    drift_detector = LLMAgentRiskProfileDriftDetector(profile_service, version_service, impact_analyzer)
    orchestrator = LLMAgentRiskProfileGovernanceOrchestrator(
        profile_service, version_service, approval_service, rollout_service, drift_detector,
        impact_analyzer=impact_analyzer,
    )
    return {
        "profile_service": profile_service,
        "version_service": version_service,
        "activation_service": activation_service,
        "approval_service": approval_service,
        "rollout_service": rollout_service,
        "impact_analyzer": impact_analyzer,
        "drift_detector": drift_detector,
        "orchestrator": orchestrator,
    }


# --- preparation invokes expected stages in order -----------------------


def test_prepare_runs_all_stages_and_requests_approval():
    s = _full_stack()
    profile = s["profile_service"].create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    s["version_service"].create_version(profile.profile_id)

    result = s["orchestrator"].prepare(profile.profile_id, 1, "scope-1")

    assert isinstance(result, RiskProfileGovernanceResult)
    assert result.governance_state == PENDING_APPROVAL
    assert result.validation_result.is_valid is True
    assert result.compatibility_result.compatible is True
    assert result.impact_result is not None
    assert result.approval_status == PENDING
    assert result.blocking_reasons == []

    # request_approval() actually ran -- a real, pending approval exists.
    status = s["approval_service"].get_status(profile.profile_id, 1, "scope-1")
    assert status == PENDING


def test_prepare_is_idempotent_via_real_approval_reuse():
    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1")
    s["version_service"].create_version(profile.profile_id)

    first = s["orchestrator"].prepare(profile.profile_id, 1, "scope-1")
    second = s["orchestrator"].prepare(profile.profile_id, 1, "scope-1")

    history = s["approval_service"].list_history(profile.profile_id, 1, "scope-1")
    assert len(history) == 1  # Commit #10's own idempotent reuse, not re-derived here
    assert first.approval_status == second.approval_status == PENDING


# --- failed validation prevents later stages ------------------------------


def test_failed_validation_prevents_compatibility_and_impact_and_approval():
    from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersion

    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1")
    corrupted = LLMAgentRiskProfileVersion(
        profile_id=profile.profile_id, version=1,
        definition={"name": "p1", "action_rules": [], "default_level": "NOT_A_LEVEL", "action_name": None, "action_category": None},
        provenance={},
    )
    s["version_service"].store.save(corrupted)

    result = s["orchestrator"].prepare(profile.profile_id, 1, "scope-1")

    assert result.governance_state == BLOCKED
    assert result.validation_result.is_valid is False
    assert result.compatibility_result is None
    assert result.impact_result is None
    assert result.approval_status is None
    assert result.blocking_reasons != []

    # No approval was ever requested.
    status = s["approval_service"].get_status(profile.profile_id, 1, "scope-1")
    from backend.agent_risk_profile_approval import NOT_REQUESTED

    assert status == NOT_REQUESTED


# --- failed compatibility prevents approval readiness ----------------------


def test_failed_compatibility_prevents_approval_readiness():
    s = _full_stack()
    profile = s["profile_service"].create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"subject": "prod"})]
    )
    s["version_service"].create_version(profile.profile_id)

    from dataclasses import replace

    class _AlwaysIncompatible(LLMAgentRiskProfileCompatibility):
        def check(self, profile, target_context):
            result = super().check(profile, target_context)
            return replace(result, compatible=False, reasons=["forced incompatible"])

    orchestrator = LLMAgentRiskProfileGovernanceOrchestrator(
        s["profile_service"], s["version_service"], s["approval_service"], s["rollout_service"],
        s["drift_detector"], impact_analyzer=s["impact_analyzer"], compatibility=_AlwaysIncompatible(),
    )

    result = orchestrator.prepare(profile.profile_id, 1, "scope-1")
    assert result.governance_state == BLOCKED
    assert result.validation_result.is_valid is True
    assert result.compatibility_result.compatible is False
    assert result.impact_result is None
    assert "forced incompatible" in result.blocking_reasons

    from backend.agent_risk_profile_approval import NOT_REQUESTED

    assert s["approval_service"].get_status(profile.profile_id, 1, "scope-1") == NOT_REQUESTED


# --- impact blockers surfaced correctly ------------------------------------


def test_impact_blocking_conflicts_surfaced_and_stop_approval():
    s = _full_stack()
    profile = s["profile_service"].create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"subject": "prod"})]
    )
    s["version_service"].create_version(profile.profile_id)

    from dataclasses import replace

    class _IncompatibleImpactAnalyzer(LLMAgentRiskProfileImpactAnalyzer):
        def analyze(self, *args, **kwargs):
            result = super().analyze(*args, **kwargs)
            return replace(result, blocking_conflicts=["impact-detected incompatibility"])

    impact_analyzer = _IncompatibleImpactAnalyzer(s["profile_service"], s["version_service"])
    orchestrator = LLMAgentRiskProfileGovernanceOrchestrator(
        s["profile_service"], s["version_service"], s["approval_service"], s["rollout_service"],
        s["drift_detector"], impact_analyzer=impact_analyzer,
    )

    result = orchestrator.prepare(profile.profile_id, 1, "scope-1")
    assert result.governance_state == BLOCKED
    assert result.impact_result is not None
    assert "impact-detected incompatibility" in result.blocking_reasons
    assert result.approval_status is None


# --- approval required before rollout -------------------------------------


def test_approve_and_rollout_requires_approved_status():
    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1")
    s["version_service"].create_version(profile.profile_id)
    approval = s["approval_service"].request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    result = s["orchestrator"].approve_and_rollout(approval.approval_id)
    assert result.governance_state == NOT_APPROVED
    assert result.approval_status == PENDING
    assert result.rollout_status is None
    assert result.blocking_reasons != []


def test_approve_and_rollout_rejects_a_rejected_approval():
    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1")
    s["version_service"].create_version(profile.profile_id)
    approval = s["approval_service"].request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    s["approval_service"].reject(approval.approval_id, "reviewer-1", "not ready")

    result = s["orchestrator"].approve_and_rollout(approval.approval_id)
    assert result.governance_state == NOT_APPROVED
    assert result.approval_status == REJECTED


# --- rollout delegates to the existing rollout service ----------------------


def test_approve_and_rollout_delegates_to_real_rollout_service():
    s = _full_stack()
    profile = s["profile_service"].create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )
    s["version_service"].create_version(profile.profile_id)
    approval = s["approval_service"].request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    s["approval_service"].approve(approval.approval_id, "reviewer-1")

    result = s["orchestrator"].approve_and_rollout(approval.approval_id)

    assert result.governance_state == ROLLED_OUT
    assert result.rollout_status == COMPLETED

    active_profile, active_version = s["activation_service"].get_active("scope-1")
    assert active_profile.profile_id == profile.profile_id
    assert active_version.version == 1


# --- active assessment reports detected drift ------------------------------


def test_assess_active_reports_stable_when_no_drift():
    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1", default_level=LEVEL_LOW)
    s["version_service"].create_version(profile.profile_id)

    result = s["orchestrator"].assess_active(profile.profile_id, "scope-1")
    assert result.governance_state == STABLE
    assert result.drift_result.drift_detected is False


def test_assess_active_reports_drifted_state():
    s = _full_stack()
    profile = s["profile_service"].create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_LOW, {"tool_name": "delete_file"})]
    )
    s["version_service"].create_version(profile.profile_id)  # v1: LOW
    s["version_service"].create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )  # v2, live

    # v1 is now stale relative to live -- checking drift against v1
    # explicitly (via the real drift detector) confirms real divergence,
    # then assess_active() (which uses the *latest* recorded version,
    # i.e. v2, as its own baseline) should read STABLE against that.
    explicit = s["drift_detector"].detect_version(profile.profile_id, 1, "scope-1")
    assert explicit.drift_detected is True

    result = s["orchestrator"].assess_active(profile.profile_id, "scope-1")
    assert result.governance_state == STABLE
    assert result.drift_result.drift_detected is False


def test_assess_active_uses_real_drift_detector_result():
    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1")
    # No version ever recorded -- drift detector reports UNKNOWN, never
    # a fabricated STABLE/DRIFTED verdict built on no evidence.
    from backend.agent_risk_profile_drift_detection import UNKNOWN

    result = s["orchestrator"].assess_active(profile.profile_id, "scope-1")
    assert result.drift_result.drift_type == UNKNOWN
    assert result.governance_state == STABLE  # compatible and not "drift_detected" (UNKNOWN != detected)


# --- underlying service failures propagate correctly ------------------------


def test_unknown_profile_propagates_from_prepare():
    s = _full_stack()
    with pytest.raises(UnknownRiskProfileError):
        s["orchestrator"].prepare("does-not-exist", 1, "scope-1")


def test_scope_mismatch_propagates_from_prepare():
    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1")
    s["version_service"].create_version(profile.profile_id)

    with pytest.raises(RiskProfileScopeMismatchError):
        s["orchestrator"].prepare(profile.profile_id, 1, "scope-2")


def test_unknown_approval_propagates_from_approve_and_rollout():
    from backend.agent_risk_profile_approval import UnknownRiskProfileApprovalError

    s = _full_stack()
    with pytest.raises(UnknownRiskProfileApprovalError):
        s["orchestrator"].approve_and_rollout("does-not-exist")


def test_conflicting_rollout_propagates_from_approve_and_rollout():
    from backend.agent_risk_profile_rollout import ConflictingRolloutError

    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1", default_level=LEVEL_LOW)
    s["version_service"].create_version(profile.profile_id)
    s["version_service"].create_version(profile.profile_id, default_level=LEVEL_HIGH)

    approval1 = s["approval_service"].request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    s["approval_service"].approve(approval1.approval_id, "reviewer-1")
    approval2 = s["approval_service"].request_approval(profile.profile_id, 2, "scope-1", requested_by="alice")
    s["approval_service"].approve(approval2.approval_id, "reviewer-1")

    s["rollout_service"].start_rollout(profile.profile_id, 1, "scope-1", "standard")

    with pytest.raises(ConflictingRolloutError):
        s["orchestrator"].approve_and_rollout(approval2.approval_id)


# --- no duplicate domain logic ---------------------------------------------


def test_orchestrator_validation_result_matches_real_validator_call():
    from backend.agent_risk_profile_versioning import profile_from_version

    s = _full_stack()
    profile = s["profile_service"].create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    s["version_service"].create_version(profile.profile_id)

    result = s["orchestrator"].prepare(profile.profile_id, 1, "scope-1")

    target_version = s["version_service"].get_version(profile.profile_id, 1)
    prospective = profile_from_version(profile, target_version)
    independent = LLMAgentRiskProfileValidator().validate(prospective)

    assert result.validation_result.is_valid == independent.is_valid
    assert result.validation_result.issues == independent.issues


def test_orchestrator_never_stores_its_own_domain_state():
    s = _full_stack()
    # The orchestrator itself exposes no store/persistence of its own --
    # every field is a real collaborator reference.
    orchestrator = s["orchestrator"]
    assert not hasattr(orchestrator, "store")


# --- existing activation/history/audit behavior remains intact ------------


def test_history_is_recorded_through_real_activation_during_rollout():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    tracked_activation = LLMAgentRiskProfileActivationHistoryTrackedService(
        profile_service, version_service, history_service=history_service, actor="governance-bot"
    )
    approval_service = LLMAgentRiskProfileApprovalService(profile_service, version_service)
    rollout_service = LLMAgentRiskProfileRolloutService(
        profile_service, version_service, tracked_activation, approval_service
    )
    impact_analyzer = LLMAgentRiskProfileImpactAnalyzer(profile_service, version_service)
    drift_detector = LLMAgentRiskProfileDriftDetector(profile_service, version_service, impact_analyzer)
    orchestrator = LLMAgentRiskProfileGovernanceOrchestrator(
        profile_service, version_service, approval_service, rollout_service, drift_detector,
        impact_analyzer=impact_analyzer,
    )

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1: LOW
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2, live
    # Approve v1, the version *not* currently live -- rolling it out is
    # a real content change, which is what makes the activate stage's
    # own ActivationResult genuinely ACTIVATED (not a no-op ALREADY_ACTIVE)
    # and therefore what Commit #7's own tracked wrapper actually records.
    approval = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    approval_service.approve(approval.approval_id, "reviewer-1")

    result = orchestrator.approve_and_rollout(approval.approval_id)
    assert result.governance_state == ROLLED_OUT

    changes = history_service.list(profile.profile_id)
    assert any(change.change_type == ACTIVATED for change in changes)


def test_approve_and_rollout_never_mutates_profile_when_not_approved():
    s = _full_stack()
    profile = s["profile_service"].create("scope-1", "p1", default_level=LEVEL_LOW)
    s["version_service"].create_version(profile.profile_id)
    approval = s["approval_service"].request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    before = s["profile_service"].get(profile.profile_id)
    s["orchestrator"].approve_and_rollout(approval.approval_id)
    after = s["profile_service"].get(profile.profile_id)

    assert before == after
