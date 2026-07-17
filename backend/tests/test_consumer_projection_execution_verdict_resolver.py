from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason,
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport,
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason,
    ResearchWorkspaceConsumerProjectionExecutionVerdictResolver,
)


AUTHORIZED = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.AUTHORIZED
)
CONDITIONAL_AUTHORIZATION = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.CONDITIONAL
)
DENIED = ResearchWorkspaceConsumerProjectionExecutionAuthorization.DENIED

GATE_OPEN = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.GATE_OPEN
)
APPROVAL_PENDING = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.APPROVAL_PENDING
)
GATE_CLOSED = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.GATE_CLOSED
)

APPROVED = ResearchWorkspaceConsumerProjectionExecutionVerdict.APPROVED
PENDING = ResearchWorkspaceConsumerProjectionExecutionVerdict.PENDING
REJECTED = ResearchWorkspaceConsumerProjectionExecutionVerdict.REJECTED

AUTHORIZED_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason.AUTHORIZED
)
APPROVAL_REQUIRED = (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason.APPROVAL_REQUIRED
)
AUTHORIZATION_DENIED = (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason.AUTHORIZATION_DENIED
)


def _make_authorization(
    *,
    projection_name="workspace.bootstrap",
    authorization=AUTHORIZED,
    reason=GATE_OPEN,
    authorized=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport(
        projection_name=projection_name,
        authorization=authorization,
        reason=reason,
        authorized=authorized,
    )


class TestAuthorized:
    """AUTHORIZED resolves to APPROVED with approved=True."""

    def test_authorized_produces_approved(self):
        authorization = _make_authorization(
            authorization=AUTHORIZED, reason=GATE_OPEN, authorized=True
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()
        report = resolver.resolve(authorization)

        assert report.verdict == APPROVED
        assert report.reason == AUTHORIZED_REASON
        assert report.approved is True


class TestConditional:
    """CONDITIONAL resolves to PENDING with approved=False."""

    def test_conditional_produces_pending(self):
        authorization = _make_authorization(
            authorization=CONDITIONAL_AUTHORIZATION,
            reason=APPROVAL_PENDING,
            authorized=False,
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()
        report = resolver.resolve(authorization)

        assert report.verdict == PENDING
        assert report.reason == APPROVAL_REQUIRED
        assert report.approved is False


class TestDenied:
    """DENIED resolves to REJECTED with approved=False."""

    def test_denied_produces_rejected(self):
        authorization = _make_authorization(
            authorization=DENIED, reason=GATE_CLOSED, authorized=False
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()
        report = resolver.resolve(authorization)

        assert report.verdict == REJECTED
        assert report.reason == AUTHORIZATION_DENIED
        assert report.approved is False


class TestProjectionPreserved:
    """projection_name is copied from the authorization report."""

    def test_projection_name_is_preserved(self):
        authorization = _make_authorization(
            projection_name="workspace.attention"
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()
        report = resolver.resolve(authorization)

        assert report.projection_name == "workspace.attention"


class TestDeterminism:
    """Resolving the same authorization report twice yields equal reports."""

    def test_equivalent_authorization_produces_equivalent_reports(self):
        authorization = _make_authorization(
            authorization=CONDITIONAL_AUTHORIZATION, reason=APPROVAL_PENDING
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()

        first = resolver.resolve(authorization)
        second = resolver.resolve(authorization)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_authorization(self):
        authorization = _make_authorization(
            authorization=CONDITIONAL_AUTHORIZATION, reason=APPROVAL_PENDING
        )
        authorization_dict_before = authorization.to_dict()

        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()
        resolver.resolve(authorization)

        assert authorization.to_dict() == authorization_dict_before

    def test_report_carries_no_execution_or_scheduler_state(self):
        authorization = _make_authorization(
            authorization=AUTHORIZED, reason=GATE_OPEN
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionVerdictResolver()
        report = resolver.resolve(authorization)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "verdict",
            "reason",
            "approved",
        }
