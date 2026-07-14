from backend.session import (
    ResearchIntegrityReport,
    ResearchWorkspaceCapabilities,
    ResearchWorkspaceReadinessAssessor,
    ResearchWorkspaceReadinessStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


class HealthySessionManager:

    def list_sessions(self):

        return []


class BrokenSessionManager:

    def list_sessions(self):

        raise RuntimeError(
            "session store unavailable"
        )


class HealthyIntegrityAuditor:

    def audit(self):

        return ResearchIntegrityReport()


class BrokenIntegrityAuditor:

    def audit(self):

        raise RuntimeError(
            "integrity audit failed"
        )


class HealthyChangeFeed:

    @property
    def latest_sequence(self):

        return 0


class UnreachableChangeFeed:

    @property
    def latest_sequence(self):

        raise AssertionError(
            "change_feed check should not run "
            "when the capability is disabled"
        )


def create_assessor(

    session_manager=None,

    integrity_auditor=None,

    change_feed=None,

    capability_registry=None,

):

    return (

        ResearchWorkspaceReadinessAssessor(

            capability_registry=(

                capability_registry

                or ResearchWorkspaceCapabilities()
            ),

            session_manager=(

                session_manager

                or HealthySessionManager()
            ),

            integrity_auditor=(

                integrity_auditor

                or HealthyIntegrityAuditor()
            ),

            change_feed=(

                change_feed

                or HealthyChangeFeed()
            ),
        )
    )


def test_fully_healthy_workspace_is_ready():

    assessor = create_assessor()

    assessment = assessor.assess()

    assert (

        assessment.status

        == ResearchWorkspaceReadinessStatus
        .READY
    )

    assert assessment.ready is True

    assert assessment.blocking is False

    assert assessment.warnings == []

    assert assessment.blocking_reasons == []


def test_optional_warning_produces_degraded_state():

    assessor = create_assessor(
        change_feed=UnreachableChangeFeed(),
    )

    assessment = assessor.assess()

    assert (

        assessment.status

        == ResearchWorkspaceReadinessStatus
        .DEGRADED
    )

    assert assessment.ready is True

    assert assessment.blocking is False

    assert len(assessment.warnings) == 1


def test_critical_failure_produces_unavailable_state():

    assessor = create_assessor(
        session_manager=BrokenSessionManager(),
    )

    assessment = assessor.assess()

    assert (

        assessment.status

        == ResearchWorkspaceReadinessStatus
        .UNAVAILABLE
    )

    assert assessment.ready is False

    assert assessment.blocking is True

    assert (

        "Research session workspace "
        "could not be accessed."

        in assessment.blocking_reasons
    )


def test_disabled_capability_is_not_treated_as_broken():

    capabilities = (
        ResearchWorkspaceCapabilities()
    )

    capabilities.get_capability(
        "change_feed"
    ).enabled = False

    assessor = create_assessor(
        capability_registry=capabilities,

        change_feed=UnreachableChangeFeed(),
    )

    assessment = assessor.assess()

    assert not any(

        check.name == "change_feed"

        for check

        in assessment.checks
    )

    assert (

        assessment.status

        == ResearchWorkspaceReadinessStatus
        .READY
    )


def test_optional_check_exception_is_isolated():

    assessor = create_assessor(
        integrity_auditor=BrokenIntegrityAuditor(),
    )

    assessment = assessor.assess()

    checks_by_name = {

        check.name: check

        for check

        in assessment.checks
    }

    assert (
        checks_by_name[
            "session_workspace"
        ].status.value

        == "pass"
    )

    assert (
        checks_by_name[
            "workspace_integrity"
        ].status.value

        == "warning"
    )

    assert (
        checks_by_name[
            "change_feed"
        ].status.value

        == "pass"
    )

    assert (

        assessment.status

        == ResearchWorkspaceReadinessStatus
        .DEGRADED
    )


def test_critical_check_exception_blocks_readiness():

    assessor = create_assessor(
        session_manager=BrokenSessionManager(),
    )

    assessment = assessor.assess()

    assert (

        assessment.status

        == ResearchWorkspaceReadinessStatus
        .UNAVAILABLE
    )

    assert assessment.blocking is True


def test_readiness_assessment_is_read_only():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    before_session_count = len(
        application
        .session_manager
        .list_sessions()
    )

    before_sequence = (

        application
        .research_workspace_change_feed
        .latest_sequence
    )

    before_findings = len(

        application
        .research_workspace_integrity_auditor
        .audit()
        .findings
    )

    application.research_workspace.assess_readiness()

    application.research_workspace.assess_readiness()

    after_session_count = len(
        application
        .session_manager
        .list_sessions()
    )

    after_sequence = (

        application
        .research_workspace_change_feed
        .latest_sequence
    )

    after_findings = len(

        application
        .research_workspace_integrity_auditor
        .audit()
        .findings
    )

    assert (
        before_session_count
        == after_session_count
    )

    assert before_sequence == after_sequence

    assert before_findings == after_findings


def test_gateway_exposes_readiness():

    application = (
        PreReqAIApplication()
    )

    gateway_assessment = (

        application
        .research_workspace
        .assess_readiness()
    )

    direct_assessment = (

        application
        .research_workspace_readiness_assessor
        .assess()
    )

    assert (
        gateway_assessment.status

        == direct_assessment.status
    )

    assert (
        gateway_assessment.ready

        == direct_assessment.ready
    )

    assert (
        gateway_assessment.blocking

        == direct_assessment.blocking
    )


def test_serialization_uses_primitive_values():

    assessor = create_assessor(
        change_feed=UnreachableChangeFeed(),
    )

    assessment = assessor.assess()

    payload = assessment.to_dict()

    assert (
        payload["status"]

        == "degraded"
    )

    change_feed_payload = next(

        check

        for check

        in payload["checks"]

        if check["name"] == "change_feed"
    )

    assert (
        change_feed_payload["status"]

        == "warning"
    )

    assert (
        change_feed_payload["capability"]

        == "change_feed"
    )

    assert isinstance(
        payload["status"],
        str,
    )
