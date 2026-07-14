from types import (
    SimpleNamespace,
)

from backend.session import (
    ResearchIntegrityFinding,
    ResearchIntegrityReport,
    ResearchIntegritySeverity,
    ResearchSessionActivitySummary,
    ResearchWorkspaceAttentionCategory,
    ResearchWorkspaceAttentionProjector,
    ResearchWorkspaceAttentionSeverity,
    ResearchWorkspaceReadinessAssessment,
    ResearchWorkspaceReadinessStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def make_readiness(

    status,

    warnings=(),

    blocking_reasons=(),

):

    return (

        ResearchWorkspaceReadinessAssessment(

            status=status,

            ready=(

                status

                != ResearchWorkspaceReadinessStatus
                .UNAVAILABLE
            ),

            blocking=(

                status

                == ResearchWorkspaceReadinessStatus
                .UNAVAILABLE
            ),

            checks=[],

            warnings=list(
                warnings
            ),

            blocking_reasons=list(
                blocking_reasons
            ),
        )
    )


class FakeReadinessAssessor:

    def __init__(

        self,

        assessment,

    ):

        self.assessment = (
            assessment
        )

    def assess(self):

        return self.assessment


class FakeIntegrityAuditor:

    def __init__(

        self,

        report=None,

    ):

        self.report = (

            report

            or ResearchIntegrityReport()
        )

    def audit(self):

        return self.report


class FakeInsightsService:

    def __init__(

        self,

        dormant_sessions=(),

    ):

        self._dormant_sessions = list(
            dormant_sessions
        )

    def build_insights(

        self,

        **kwargs,

    ):

        return (

            SimpleNamespace(
                dormant_sessions=(

                    self
                    ._dormant_sessions
                )
            )
        )


def dormant_summary(

    session_id="session-842",

    display_name="Spectral Route",

    lifecycle_status="paused",

):

    return (

        ResearchSessionActivitySummary(

            session_id=session_id,

            display_name=display_name,

            lifecycle_status=(
                lifecycle_status
            ),

            archived=False,

            last_activity_at=None,

            activity_count=0,
        )
    )


def create_projector(

    readiness=None,

    integrity_report=None,

    dormant_sessions=(),

):

    return (

        ResearchWorkspaceAttentionProjector(

            readiness_assessor=(

                FakeReadinessAssessor(

                    readiness

                    or make_readiness(

                        ResearchWorkspaceReadinessStatus
                        .READY
                    )
                )
            ),

            integrity_auditor=(

                FakeIntegrityAuditor(
                    integrity_report
                )
            ),

            insights_service=(

                FakeInsightsService(
                    dormant_sessions
                )
            ),
        )
    )


def test_healthy_workspace_produces_no_attention_noise():

    projector = create_projector()

    projection = projector.project()

    assert projection.items == []

    assert projection.total_count == 0

    assert projection.actionable_count == 0

    assert projection.critical_count == 0

    assert projection.high_count == 0


def test_degraded_readiness_produces_medium_attention():

    projector = create_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .DEGRADED,

            warnings=[
                "Reactive synchronization "
                "is unavailable."
            ],
        ),
    )

    projection = projector.project()

    assert projection.total_count == 1

    item = projection.items[0]

    assert (
        item.category

        == ResearchWorkspaceAttentionCategory
        .READINESS
    )

    assert (
        item.severity

        == ResearchWorkspaceAttentionSeverity
        .MEDIUM
    )

    assert item.actionable is True


def test_unavailable_workspace_produces_critical_attention():

    projector = create_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .UNAVAILABLE,

            blocking_reasons=[
                "Core research session "
                "workspace could not be "
                "accessed."
            ],
        ),
    )

    projection = projector.project()

    item = projection.items[0]

    assert (
        item.severity

        == ResearchWorkspaceAttentionSeverity
        .CRITICAL
    )

    assert projection.critical_count == 1

    assert (
        "Core research session workspace "
        "could not be accessed."

        == item.message
    )


def test_integrity_issue_produces_attention_item():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="broken_lineage_reference",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message=(
                        "The session references "
                        "a parent that does not "
                        "exist."
                    ),

                    entity_type="research_session",

                    entity_id="session-842",
                ),
            ],
        )
    )

    projector = create_projector(
        integrity_report=report,
    )

    projection = projector.project()

    item = projection.items[0]

    assert (
        item.category

        == ResearchWorkspaceAttentionCategory
        .INTEGRITY
    )

    assert (
        item.entity_id

        == "session-842"
    )

    assert (
        item.severity

        == ResearchWorkspaceAttentionSeverity
        .HIGH
    )


def test_stable_attention_ids():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="missing_profile",

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message=(
                        "Research session has no "
                        "profile."
                    ),

                    entity_type="research_session",

                    entity_id="session-1",
                ),
            ],
        )
    )

    projector = create_projector(
        integrity_report=report,
    )

    first = projector.project()

    second = projector.project()

    assert (

        {
            item.attention_id

            for item

            in first.items
        }

        == {
            item.attention_id

            for item

            in second.items
        }
    )


def test_severity_ordering_is_deterministic():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="issue_a",

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message="warning issue",

                    entity_id="session-a",
                ),

                ResearchIntegrityFinding(

                    code="issue_b",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message="error issue",

                    entity_id="session-b",
                ),

                ResearchIntegrityFinding(

                    code="issue_c",

                    severity=(

                        ResearchIntegritySeverity
                        .CRITICAL
                    ),

                    message="critical issue",

                    entity_id="session-c",
                ),
            ],
        )
    )

    projector = create_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .DEGRADED,

            warnings=["degraded"],
        ),

        integrity_report=report,

        dormant_sessions=[
            dormant_summary()
        ],
    )

    projection = projector.project()

    severities = [

        item.severity

        for item

        in projection.items
    ]

    assert severities == [

        ResearchWorkspaceAttentionSeverity
        .CRITICAL,

        ResearchWorkspaceAttentionSeverity
        .HIGH,

        ResearchWorkspaceAttentionSeverity
        .MEDIUM,

        ResearchWorkspaceAttentionSeverity
        .MEDIUM,

        ResearchWorkspaceAttentionSeverity
        .LOW,
    ]


def test_minimum_severity_filtering():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="issue_a",

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message="warning issue",

                    entity_id="session-a",
                ),

                ResearchIntegrityFinding(

                    code="issue_b",

                    severity=(

                        ResearchIntegritySeverity
                        .CRITICAL
                    ),

                    message="critical issue",

                    entity_id="session-b",
                ),
            ],
        )
    )

    projector = create_projector(
        integrity_report=report,
    )

    projection = projector.project(

        minimum_severity=(

            ResearchWorkspaceAttentionSeverity
            .HIGH
        ),
    )

    severities = {

        item.severity

        for item

        in projection.items
    }

    assert severities == {

        ResearchWorkspaceAttentionSeverity
        .CRITICAL
    }


def test_category_filtering():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="issue_a",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message="integrity issue",

                    entity_id="session-a",
                ),
            ],
        )
    )

    projector = create_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .DEGRADED,

            warnings=["degraded"],
        ),

        integrity_report=report,
    )

    projection = projector.project(

        category=(

            ResearchWorkspaceAttentionCategory
            .INTEGRITY
        ),
    )

    assert len(
        projection.items
    ) == 1

    assert (

        projection.items[0].category

        == ResearchWorkspaceAttentionCategory
        .INTEGRITY
    )


def test_actionable_filtering():

    projector = create_projector(

        readiness=make_readiness(

            ResearchWorkspaceReadinessStatus
            .DEGRADED,

            warnings=["degraded"],
        ),
    )

    projection = projector.project(
        actionable_only=True,
    )

    assert len(
        projection.items
    ) == 1

    assert projection.items[0].actionable


def test_limit_is_applied_after_priority_ordering():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="issue_a",

                    severity=(

                        ResearchIntegritySeverity
                        .ERROR
                    ),

                    message="error issue",

                    entity_id="session-a",
                ),

                ResearchIntegrityFinding(

                    code="issue_b",

                    severity=(

                        ResearchIntegritySeverity
                        .CRITICAL
                    ),

                    message="critical issue",

                    entity_id="session-b",
                ),
            ],
        )
    )

    projector = create_projector(
        integrity_report=report,
    )

    projection = projector.project(
        limit=2,
    )

    assert len(
        projection.items
    ) == 2

    assert (

        projection.items[0].severity

        == ResearchWorkspaceAttentionSeverity
        .CRITICAL
    )

    assert (

        projection.items[1].severity

        == ResearchWorkspaceAttentionSeverity
        .HIGH
    )


def test_duplicate_attention_ids_are_deduplicated():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="missing_profile",

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message="first occurrence",

                    entity_id="session-1",
                ),

                ResearchIntegrityFinding(

                    code="missing_profile",

                    severity=(

                        ResearchIntegritySeverity
                        .WARNING
                    ),

                    message="second occurrence",

                    entity_id="session-1",
                ),
            ],
        )
    )

    projector = create_projector(
        integrity_report=report,
    )

    projection = projector.project()

    assert projection.total_count == 1


def test_projection_is_read_only():

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

    before_activity_count = len(

        application
        .research_activity_store
        .list_all()
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

    application.research_workspace.get_attention()

    application.research_workspace.get_attention()

    after_session_count = len(

        application
        .session_manager
        .list_sessions()
    )

    after_activity_count = len(

        application
        .research_activity_store
        .list_all()
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

    assert (
        before_activity_count

        == after_activity_count
    )

    assert before_sequence == after_sequence

    assert before_findings == after_findings


def test_gateway_exposes_attention_projection():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    gateway_projection = (

        application
        .research_workspace
        .get_attention()
    )

    direct_projection = (

        application
        .research_workspace_attention_projector
        .project()
    )

    assert (

        gateway_projection.total_count

        == direct_projection.total_count
    )

    assert (

        {
            item.attention_id

            for item

            in gateway_projection.items
        }

        == {
            item.attention_id

            for item

            in direct_projection.items
        }
    )


def test_bootstrap_includes_bounded_attention_summary():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    full_attention = (

        application
        .research_workspace_attention_projector
        .project()
    )

    assert (

        projection.attention.total_count

        == full_attention.total_count
    )

    assert len(

        projection.attention.top_items

    ) <= 3

    assert len(

        projection.attention.top_items

    ) <= len(
        full_attention.items
    )


def test_serialization_uses_primitive_values():

    report = (

        ResearchIntegrityReport(
            findings=[

                ResearchIntegrityFinding(

                    code="missing_profile",

                    severity=(

                        ResearchIntegritySeverity
                        .CRITICAL
                    ),

                    message="critical issue",

                    entity_id="session-1",
                ),
            ],
        )
    )

    projector = create_projector(
        integrity_report=report,
    )

    projection = projector.project()

    payload = projection.to_dict()

    item = payload["items"][0]

    assert item["severity"] == "critical"

    assert item["category"] == "integrity"

    assert isinstance(
        item["severity"],
        str,
    )

    assert isinstance(
        item["category"],
        str,
    )
