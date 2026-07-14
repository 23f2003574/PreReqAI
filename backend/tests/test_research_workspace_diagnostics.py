import pytest

from backend.session import (
    ResearchWorkspaceConsumerContractVersion,
    ResearchWorkspaceConsumerProjectionDiagnosticStageKind,
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
    ResearchWorkspaceConsumerProjectionDiagnosticsCollector,
    ResearchWorkspaceProjectionContext,
)

from frontend.src.app import (
    PreReqAIApplication,
)


class FakeClock:

    def __init__(

        self,

        steps,

    ):

        self._steps = list(
            steps
        )

        self._index = 0

    def now(self):

        index = min(

            self._index,

            len(
                self._steps
            )

            - 1,
        )

        self._index += 1

        return self._steps[
            index
        ]


def create_collector(

    steps,

    operation_name="test.operation",

):

    return (

        ResearchWorkspaceConsumerProjectionDiagnosticsCollector(

            operation_name=(
                operation_name
            ),

            clock=FakeClock(
                steps
            ),
        )
    )


class CountingReadinessAssessor:

    def __init__(

        self,

        value="ready",

    ):

        self._value = value

        self.calls = 0

    def assess(self):

        self.calls += 1

        return self._value


class FlakyIntegrityAuditor:

    def __init__(

        self,

        fail_times=1,

    ):

        self._fail_times = (
            fail_times
        )

        self.calls = 0

    def audit(self):

        self.calls += 1

        if (

            self.calls

            <= self._fail_times
        ):

            raise RuntimeError(
                "integrity unavailable"
            )

        return "healthy-report"


def make_context(

    readiness_assessor=None,

    integrity_auditor=None,

    capability_registry=None,

    insights_service=None,

    session_manager=None,

    profile_store=None,

    diagnostics=None,

    clock=None,

):

    class _StubService:

        def list_capabilities(self):

            return []

        def build_insights(
            self,
            **kwargs,
        ):

            return object()

        def load_session(
            self,
            session_id,
        ):

            return None

        def get(
            self,
            session_id,
        ):

            return None

    stub = _StubService()

    return (

        ResearchWorkspaceProjectionContext(

            capability_registry=(

                capability_registry

                or stub
            ),

            readiness_assessor=(

                readiness_assessor

                or CountingReadinessAssessor()
            ),

            integrity_auditor=(

                integrity_auditor

                or FlakyIntegrityAuditor(
                    fail_times=0,
                )
            ),

            insights_service=(

                insights_service

                or stub
            ),

            session_manager=(

                session_manager

                or stub
            ),

            profile_store=(

                profile_store

                or stub
            ),

            diagnostics=diagnostics,

            clock=clock,
        )
    )


def populate_active_session(

    application,

    session_id="session-a",

):

    application.activate_research_session(
        session_id
    )

    application.save_research_session(
        session_id,

        paper_title="Test Paper",
    )

    application.update_research_session_profile(

        session_id,

        display_name="Session A",
    )

    return session_id


def test_collector_starts_empty():

    collector = create_collector(
        [0.0]
    )

    report = collector.finalize()

    assert report.inputs == []

    assert report.stages == []


def test_successful_stage_is_recorded():

    collector = create_collector(
        [0.0, 0.0, 0.05]
    )

    with collector.stage(

        name="test.stage",

        kind=(

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .PROJECTION
        ),
    ):

        pass

    report = collector.finalize()

    assert len(
        report.stages
    ) == 1

    stage = report.stages[0]

    assert (
        stage.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .SUCCEEDED
    )

    assert stage.duration_ms == (
        50.0
    )


def test_failed_stage_is_recorded_and_exception_reraised():

    collector = create_collector(
        [0.0, 0.01]
    )

    with pytest.raises(
        ValueError,
    ):

        with collector.stage(

            name="test.stage",

            kind=(

                ResearchWorkspaceConsumerProjectionDiagnosticStageKind
                .PROJECTION
            ),
        ):

            raise ValueError(
                "boom"
            )

    report = collector.finalize()

    assert (
        report.stages[0].status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .FAILED
    )

    assert (
        report.stages[0].failure
        .error_type

        == "ValueError"
    )


def test_degraded_stage_can_be_marked_explicitly():

    collector = create_collector(
        [0.0, 0.01]
    )

    with collector.stage(

        name="test.stage",

        kind=(

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .ASSEMBLY
        ),

    ) as stage:

        stage.mark_degraded(
            reason_code=(
                "optional_unavailable"
            ),
        )

    report = collector.finalize()

    assert (
        report.stages[0].status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .DEGRADED
    )

    assert (
        report.stages[0].reason_code

        == "optional_unavailable"
    )


def test_input_resolution_is_recorded():

    collector = create_collector(
        [0.0, 0.01]
    )

    context = make_context(
        diagnostics=collector,
    )

    context.get_readiness()

    report = collector.finalize()

    entry = report.inputs[0]

    assert (
        entry.name

        == "workspace.readiness"
    )

    assert entry.resolution_count == 1

    assert entry.reuse_count == 0


def test_input_reuse_is_recorded():

    readiness_assessor = (
        CountingReadinessAssessor()
    )

    collector = create_collector(
        [0.0, 0.01, 0.02, 0.03]
    )

    context = make_context(
        readiness_assessor=(
            readiness_assessor
        ),

        diagnostics=collector,
    )

    context.get_readiness()

    context.get_readiness()

    context.get_readiness()

    report = collector.finalize()

    entry = report.inputs[0]

    assert entry.resolution_count == 1

    assert entry.reuse_count == 2


def test_underlying_readiness_service_still_runs_once():

    readiness_assessor = (
        CountingReadinessAssessor()
    )

    collector = create_collector(
        [0.0, 0.01, 0.02, 0.03]
    )

    context = make_context(
        readiness_assessor=(
            readiness_assessor
        ),

        diagnostics=collector,
    )

    context.get_readiness()

    context.get_readiness()

    context.get_readiness()

    assert readiness_assessor.calls == 1


def test_different_inputs_are_tracked_independently():

    collector = create_collector(
        [0.0] * 10
    )

    context = make_context(
        diagnostics=collector,
    )

    context.get_readiness()

    context.get_capabilities()

    context.get_integrity_report()

    report = collector.finalize()

    names = {

        entry.name

        for entry

        in report.inputs
    }

    assert names == {
        "workspace.readiness",

        "workspace.capabilities",

        "workspace.integrity",
    }


def test_session_keys_are_tracked_independently():

    class StubSessionManager:

        def load_session(
            self,
            session_id,
        ):

            return object()

    collector = create_collector(
        [0.0] * 10
    )

    context = make_context(
        session_manager=(
            StubSessionManager()
        ),

        diagnostics=collector,
    )

    context.get_session(
        "session-1"
    )

    context.get_session(
        "session-2"
    )

    context.get_session(
        "session-1"
    )

    report = collector.finalize()

    by_key = {

        entry.key: entry

        for entry

        in report.inputs
    }

    assert (
        by_key[
            "session-1"
        ].resolution_count

        == 1
    )

    assert (
        by_key[
            "session-1"
        ].reuse_count

        == 1
    )

    assert (
        by_key[
            "session-2"
        ].resolution_count

        == 1
    )

    assert (
        by_key[
            "session-2"
        ].reuse_count

        == 0
    )


def test_failed_input_resolution_is_recorded():

    collector = create_collector(
        [0.0] * 10
    )

    context = make_context(
        integrity_auditor=(

            FlakyIntegrityAuditor(
                fail_times=5,
            )
        ),

        diagnostics=collector,
    )

    with pytest.raises(
        RuntimeError,
    ):

        context.get_integrity_report()

    report = collector.finalize()

    entry = report.inputs[0]

    assert (
        entry.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .FAILED
    )

    assert (
        entry.failure.error_type

        == "RuntimeError"
    )


def test_failed_resolution_can_be_retried():

    collector = create_collector(
        [0.0] * 10
    )

    auditor = (

        FlakyIntegrityAuditor(
            fail_times=1,
        )
    )

    context = make_context(
        integrity_auditor=auditor,

        diagnostics=collector,
    )

    with pytest.raises(
        RuntimeError,
    ):

        context.get_integrity_report()

    result = (
        context.get_integrity_report()
    )

    assert result == (
        "healthy-report"
    )

    report = collector.finalize()

    entry = report.inputs[0]

    assert entry.resolution_count == 2

    assert (
        entry.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .SUCCEEDED
    )


def test_successful_resolution_followed_by_reuse_is_not_retimed():

    shared_clock = FakeClock(

        [

            0.0,

            0.5,

            1.0,
        ],
    )

    collector = (

        ResearchWorkspaceConsumerProjectionDiagnosticsCollector(

            operation_name=(
                "test.operation"
            ),

            clock=shared_clock,
        )
    )

    context = make_context(
        diagnostics=collector,

        clock=shared_clock,
    )

    context.get_readiness()

    context.get_readiness()

    report = collector.finalize()

    entry = report.inputs[0]

    assert entry.duration_ms == (
        500.0
    )


def test_bootstrap_records_top_level_operation_duration():

    application = (
        PreReqAIApplication()
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    assert (
        result.diagnostics
        .operation_name

        == "workspace.bootstrap"
    )

    assert (
        result.diagnostics.duration_ms

        >= 0
    )


def test_bootstrap_records_nested_attention_stage():

    application = (
        PreReqAIApplication()
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    stage_names = {

        stage.name

        for stage

        in result.diagnostics.stages
    }

    assert (
        "workspace.attention.project"

        in stage_names
    )


def test_bootstrap_records_nested_action_stage():

    application = (
        PreReqAIApplication()
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    stage_names = {

        stage.name

        for stage

        in result.diagnostics.stages
    }

    assert (
        "workspace.actions.project"

        in stage_names
    )


def test_bootstrap_reuse_counts_are_correct():

    application = (
        PreReqAIApplication()
    )

    original_assess = (

        application
        .research_workspace_readiness_assessor
        .assess
    )

    calls = {
        "count": 0,
    }

    def counting_assess():

        calls[
            "count"
        ] += 1

        return original_assess()

    application.research_workspace_readiness_assessor.assess = (
        counting_assess
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    readiness_input = next(

        entry

        for entry

        in result.diagnostics.inputs

        if entry.name == "workspace.readiness"
    )

    assert readiness_input.resolution_count == 1

    assert readiness_input.reuse_count == 2

    assert calls[
        "count"
    ] == 1


def test_optional_attention_failure_produces_degraded_bootstrap_diagnostics():

    application = (
        PreReqAIApplication()
    )

    def broken_audit():

        raise RuntimeError(
            "integrity unavailable"
        )

    application.research_workspace_integrity_auditor.audit = (
        broken_audit
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    attention_stage = next(

        stage

        for stage

        in result.diagnostics.stages

        if (

            stage.name

            == "workspace.attention.project"
        )
    )

    assert (
        attention_stage.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .FAILED
    )

    assert (
        result.diagnostics.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .DEGRADED
    )

    assert result.projection is not None

    assert (

        "Attention summary could "
        "not be computed."

        in result.projection.warnings
    )


def test_full_success_produces_successful_overall_status():

    application = (
        PreReqAIApplication()
    )

    populate_active_session(
        application
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    assert (
        result.diagnostics.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .SUCCEEDED
    )


def test_fatal_unhandled_failure_is_not_converted_into_success():

    application = (
        PreReqAIApplication()
    )

    def broken_list_sessions():

        raise RuntimeError(
            "session store unavailable"
        )

    application.session_manager.list_sessions = (
        broken_list_sessions
    )

    with pytest.raises(
        RuntimeError,
    ):

        application.research_workspace.diagnose_bootstrap()


def test_two_collectors_do_not_share_state():

    collector_a = create_collector(
        [0.0, 0.01]
    )

    collector_b = create_collector(
        [0.0, 0.01]
    )

    with collector_a.stage(

        name="a.stage",

        kind=(

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .PROJECTION
        ),
    ):

        pass

    report_a = (
        collector_a.finalize()
    )

    report_b = (
        collector_b.finalize()
    )

    assert len(
        report_a.stages
    ) == 1

    assert len(
        report_b.stages
    ) == 0


def test_two_contexts_with_two_collectors_remain_independent():

    readiness_assessor = (
        CountingReadinessAssessor()
    )

    collector_a = create_collector(
        [0.0, 0.01]
    )

    collector_b = create_collector(
        [0.0, 0.01]
    )

    context_a = make_context(
        readiness_assessor=(
            readiness_assessor
        ),

        diagnostics=collector_a,
    )

    context_b = make_context(
        readiness_assessor=(
            readiness_assessor
        ),

        diagnostics=collector_b,
    )

    context_a.get_readiness()

    context_b.get_readiness()

    report_a = (
        collector_a.finalize()
    )

    report_b = (
        collector_b.finalize()
    )

    assert (
        report_a.inputs[0]
        .resolution_count

        == 1
    )

    assert (
        report_b.inputs[0]
        .resolution_count

        == 1
    )


def test_collector_finalization_produces_report():

    collector = create_collector(
        [0.0, 0.01]
    )

    with collector.stage(

        name="test.stage",

        kind=(

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .PROJECTION
        ),
    ):

        pass

    report = collector.finalize()

    assert (

        report.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .SUCCEEDED
    )


def test_recording_after_finalization_is_rejected():

    collector = create_collector(
        [0.0]
    )

    collector.finalize()

    with pytest.raises(
        RuntimeError,
    ):

        collector.record_input_reuse(
            name="workspace.readiness",
        )

    with pytest.raises(
        RuntimeError,
    ):

        with collector.stage(

            name="test.stage",

            kind=(

                ResearchWorkspaceConsumerProjectionDiagnosticStageKind
                .PROJECTION
            ),
        ):

            pass


def test_repeated_finalization_is_stable():

    collector = create_collector(
        [0.0, 0.01]
    )

    with collector.stage(

        name="test.stage",

        kind=(

            ResearchWorkspaceConsumerProjectionDiagnosticStageKind
            .PROJECTION
        ),
    ):

        pass

    report_a = (
        collector.finalize()
    )

    report_b = (
        collector.finalize()
    )

    assert report_a is report_b


def test_diagnostics_do_not_mutate_workspace_state():

    application = (
        PreReqAIApplication()
    )

    session_id = (

        populate_active_session(
            application
        )
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

    application.research_workspace.diagnose_bootstrap()

    application.research_workspace.diagnose_session_actions(
        session_id
    )

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

    assert (
        before_session_count

        == after_session_count
    )

    assert before_sequence == after_sequence


def test_normal_bootstrap_contract_remains_unchanged():

    application = (
        PreReqAIApplication()
    )

    from backend.session import (
        ResearchWorkspaceBootstrapProjection,
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    assert isinstance(

        projection,

        ResearchWorkspaceBootstrapProjection,
    )


def test_diagnostics_are_not_added_to_normal_serialized_projection():

    application = (
        PreReqAIApplication()
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    payload = projection.to_dict()

    assert (
        "diagnostics"

        not in payload
    )


def test_diagnostics_use_primitive_serialization():

    application = (
        PreReqAIApplication()
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    payload = (
        result.diagnostics.to_dict()
    )

    assert isinstance(
        payload["status"],
        str,
    )

    for stage in payload["stages"]:

        assert isinstance(
            stage["status"],
            str,
        )

        assert isinstance(
            stage["kind"],
            str,
        )


def test_raw_tracebacks_are_not_stored():

    application = (
        PreReqAIApplication()
    )

    def broken_audit():

        raise RuntimeError(
            "/very/secret/internal/path.py "
            "line 42 SECRET_TOKEN=abc123"
        )

    application.research_workspace_integrity_auditor.audit = (
        broken_audit
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    payload = (
        result.diagnostics.to_dict()
    )

    serialized = str(
        payload
    )

    assert (
        "SECRET_TOKEN"

        not in serialized
    )

    assert (
        "/very/secret/internal/path.py"

        not in serialized
    )


def test_diagnostic_stage_ordering_is_deterministic():

    application = (
        PreReqAIApplication()
    )

    populate_active_session(
        application
    )

    first = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    second = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    first_order = [

        stage.name

        for stage

        in first.diagnostics.stages
    ]

    second_order = [

        stage.name

        for stage

        in second.diagnostics.stages
    ]

    assert first_order == second_order


def test_manifest_generation_does_not_create_projection_diagnostics():

    application = (
        PreReqAIApplication()
    )

    original_create = (

        application
        .research_workspace_consumer_projection_diagnostics_factory
        .create
    )

    calls = {
        "count": 0,
    }

    def counting_create(
        **kwargs,
    ):

        calls[
            "count"
        ] += 1

        return original_create(
            **kwargs
        )

    application.research_workspace_consumer_projection_diagnostics_factory.create = (
        counting_create
    )

    application.research_workspace.get_consumer_contract_manifest()

    assert calls[
        "count"
    ] == 0


def test_diagnostics_do_not_change_compatibility_results():

    application = (
        PreReqAIApplication()
    )

    result_before = (

        application
        .research_workspace
        .check_consumer_contract_compatibility(

            "workspace.bootstrap",

            ResearchWorkspaceConsumerContractVersion(

                major=1,

                minor=0,
            ),
        )
    )

    application.research_workspace.diagnose_bootstrap()

    result_after = (

        application
        .research_workspace
        .check_consumer_contract_compatibility(

            "workspace.bootstrap",

            ResearchWorkspaceConsumerContractVersion(

                major=1,

                minor=0,
            ),
        )
    )

    assert result_before.compatible is True

    assert result_after.compatible is True
