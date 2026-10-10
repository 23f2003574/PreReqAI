import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import LLMAgentRiskProfileService, RiskProfileActionRule
from backend.agent_risk_profile_activation import IncompatibleRiskProfileVersionError, RiskProfileScopeMismatchError
from backend.agent_risk_profile_approval import (
    APPROVED,
    NOT_REQUESTED,
    PENDING,
    REJECTED,
    ArchivedRiskProfileCannotEnterApprovalError,
    InvalidApprovalTransitionError,
    InvalidRiskProfileApprovalError,
    LLMAgentRiskProfileApprovalService,
    RejectionReasonRequiredError,
    RiskProfileApproval,
    UnauthorizedApproverError,
    UnknownRiskProfileApprovalError,
)
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


def _services(**kwargs):
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    approval_service = LLMAgentRiskProfileApprovalService(profile_service, version_service, **kwargs)
    return profile_service, version_service, approval_service


# --- valid version can enter approval ------------------------------------


def test_valid_version_enters_approval():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)

    approval = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    assert isinstance(approval, RiskProfileApproval)
    assert approval.status == PENDING
    assert approval.profile_id == profile.profile_id
    assert approval.version == 1
    assert approval.scope_id == "scope-1"
    assert approval.requested_by == "alice"
    assert approval.provenance["validation"]["is_valid"] is True
    assert approval.provenance["compatibility"]["compatible"] is True


# --- invalid/incompatible version cannot -----------------------------


def test_invalid_version_cannot_enter_approval():
    from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersion

    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")

    # Hand-corrupt a stored version to bypass Commit #1's own construction-
    # time validation, the same technique this series' other commits use
    # to force a genuine Commit #3 validator rejection.
    corrupted = LLMAgentRiskProfileVersion(
        profile_id=profile.profile_id,
        version=1,
        definition={"name": "p1", "action_rules": [], "default_level": "NOT_A_LEVEL", "action_name": None, "action_category": None},
        provenance={},
    )
    version_service.store.save(corrupted)

    with pytest.raises(IncompatibleRiskProfileVersionError):
        approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")


def test_incompatible_version_cannot_enter_approval():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    from backend.agent_risk_profile_compatibility import LLMAgentRiskProfileCompatibility

    class _AlwaysIncompatible(LLMAgentRiskProfileCompatibility):
        def check(self, profile, target_context):
            result = super().check(profile, target_context)
            from dataclasses import replace

            return replace(result, compatible=False, reasons=["forced incompatible for testing"])

    approval_service = LLMAgentRiskProfileApprovalService(
        profile_service, version_service, compatibility=_AlwaysIncompatible()
    )
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(IncompatibleRiskProfileVersionError):
        approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")


# --- duplicate pending approval reused ----------------------------------


def test_duplicate_pending_approval_is_reused():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    first = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    second = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="bob")

    assert first.approval_id == second.approval_id
    assert second.requested_by == "alice"  # unchanged -- the original request is returned as-is


def test_new_request_allowed_after_prior_one_resolved():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    first = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    approval_service.approve(first.approval_id, "reviewer-1")

    second = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="carol")
    assert second.approval_id != first.approval_id
    assert second.status == PENDING


# --- approval and rejection transition state ------------------------------


def test_approve_transitions_to_approved():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    requested = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    approved = approval_service.approve(requested.approval_id, "reviewer-1")
    assert approved.status == APPROVED
    assert approved.approved_by == "reviewer-1"
    assert approved.rejected_by is None
    assert approved.resolved_at is not None


def test_reject_transitions_to_rejected():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    requested = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    rejected = approval_service.reject(requested.approval_id, "reviewer-1", "too risky")
    assert rejected.status == REJECTED
    assert rejected.rejected_by == "reviewer-1"
    assert rejected.reason == "too risky"
    assert rejected.approved_by is None


def test_get_status_reflects_current_state():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    assert approval_service.get_status(profile.profile_id, 1, "scope-1") == NOT_REQUESTED

    requested = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    assert approval_service.get_status(profile.profile_id, 1, "scope-1") == PENDING

    approval_service.approve(requested.approval_id, "reviewer-1")
    assert approval_service.get_status(profile.profile_id, 1, "scope-1") == APPROVED


def test_cannot_approve_or_reject_a_resolved_approval_again():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    requested = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    approval_service.approve(requested.approval_id, "reviewer-1")

    with pytest.raises(InvalidApprovalTransitionError):
        approval_service.approve(requested.approval_id, "reviewer-2")
    with pytest.raises(InvalidApprovalTransitionError):
        approval_service.reject(requested.approval_id, "reviewer-2", "changed my mind")


def test_unknown_approval_raises():
    _, _, approval_service = _services()
    with pytest.raises(UnknownRiskProfileApprovalError):
        approval_service.approve("does-not-exist", "reviewer-1")
    with pytest.raises(UnknownRiskProfileApprovalError):
        approval_service.get("does-not-exist")


# --- rejection requires a reason ------------------------------------------


def test_reject_without_reason_raises():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    requested = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    with pytest.raises(RejectionReasonRequiredError):
        approval_service.reject(requested.approval_id, "reviewer-1", "")
    with pytest.raises(RejectionReasonRequiredError):
        approval_service.reject(requested.approval_id, "reviewer-1", None)


def test_model_rejects_inconsistent_construction():
    with pytest.raises(InvalidRiskProfileApprovalError):
        RiskProfileApproval(
            approval_id="a1", profile_id="p1", version=1, scope_id="scope-1", status=REJECTED,
            requested_by="alice", rejected_by="reviewer-1",  # missing reason
        )


# --- archived profiles cannot be approved ------------------------------


def test_archived_profile_cannot_enter_approval():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    profile_service.archive(profile.profile_id)

    with pytest.raises(ArchivedRiskProfileCannotEnterApprovalError):
        approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")


# --- approval scoped to correct profile/version/scope -----------------


def test_scope_mismatch_raises():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(RiskProfileScopeMismatchError):
        approval_service.request_approval(profile.profile_id, 1, "scope-2", requested_by="alice")


def test_approvals_for_different_versions_are_independent():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2

    approval_v1 = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    approval_v2 = approval_service.request_approval(profile.profile_id, 2, "scope-1", requested_by="alice")

    assert approval_v1.approval_id != approval_v2.approval_id
    approval_service.approve(approval_v1.approval_id, "reviewer-1")

    assert approval_service.get_status(profile.profile_id, 1, "scope-1") == APPROVED
    assert approval_service.get_status(profile.profile_id, 2, "scope-1") == PENDING


def test_approvals_never_leak_across_scopes():
    profile_service, version_service, approval_service = _services()
    p1 = profile_service.create("scope-1", "p1")
    version_service.create_version(p1.profile_id)
    p2 = profile_service.create("scope-2", "p2")
    version_service.create_version(p2.profile_id)

    approval_service.request_approval(p1.profile_id, 1, "scope-1", requested_by="alice")
    assert approval_service.get_status(p2.profile_id, 1, "scope-2") == NOT_REQUESTED


def test_authorization_callable_enforced():
    def _only_ops(actor, scope_id):
        return actor == "ops"

    profile_service, version_service, approval_service = _services(authorized=_only_ops)
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    requested = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")

    with pytest.raises(UnauthorizedApproverError):
        approval_service.approve(requested.approval_id, "random-person")

    approved = approval_service.approve(requested.approval_id, "ops")
    assert approved.status == APPROVED


# --- historical decisions remain intact ---------------------------------


def test_historical_decisions_remain_intact_across_new_requests():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    first = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    rejected = approval_service.reject(first.approval_id, "reviewer-1", "not ready")

    second = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    approval_service.approve(second.approval_id, "reviewer-2")

    history = approval_service.list_history(profile.profile_id, 1, "scope-1")
    assert [entry.status for entry in history] == [REJECTED, APPROVED]
    # the original rejection is untouched
    original = approval_service.get(first.approval_id)
    assert original.status == REJECTED
    assert original.reason == "not ready"
    assert original == rejected


# --- approval does not unexpectedly activate or mutate the profile --------


def test_approval_never_mutates_or_activates_the_profile():
    profile_service, version_service, approval_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)

    before = profile_service.get(profile.profile_id)
    requested = approval_service.request_approval(profile.profile_id, 1, "scope-1", requested_by="alice")
    approval_service.approve(requested.approval_id, "reviewer-1")
    after = profile_service.get(profile.profile_id)

    assert before == after
    assert after.default_level == LEVEL_CRITICAL  # unchanged by approval -- still whatever v2 set it to
