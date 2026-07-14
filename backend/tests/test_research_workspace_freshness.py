from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchActivityActorType,
    ResearchActivityEvent,
    ResearchActivityPage,
    ResearchActivityType,
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
    ResearchWorkspaceConsumerProjectionDiagnosticsCollector,
    ResearchWorkspaceConsumerProjectionFreshnessEvaluator,
    ResearchWorkspaceConsumerProjectionFreshnessPolicy,
    ResearchWorkspaceConsumerProjectionFreshnessPolicyNotFoundError,
    ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry,
    ResearchWorkspaceConsumerProjectionFreshnessReason,
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
    ResearchWorkspaceConsumerProjectionUnusableFreshnessError,
    ResearchWorkspaceMonotonicClock,
    ResearchWorkspaceProjectionContext,
)

from frontend.src.app import (
    PreReqAIApplication,
)


_BASE_TIME = datetime(

    2026,

    7,

    14,

    10,

    0,

    0,

    tzinfo=timezone.utc,
)


def make_evaluator(

    fresh_for_ms=60000.0,

    usable_for_ms=300000.0,

    source_name="test.source",

    maximum_future_skew_ms=5000.0,

):

    policy = (

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name=source_name,

            fresh_for_ms=fresh_for_ms,

            usable_for_ms=usable_for_ms,
        )
    )

    registry = (

        ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry(
            policies=(
                policy,
            ),
        )
    )

    return (

        ResearchWorkspaceConsumerProjectionFreshnessEvaluator(

            policy_registry=registry,

            maximum_future_skew_ms=(
                maximum_future_skew_ms
            ),
        )
    )


def test_fresh_value_is_classified_correctly():

    evaluator = make_evaluator(
        fresh_for_ms=60000.0,

        usable_for_ms=300000.0,
    )

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            - timedelta(
                seconds=30,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .FRESH
    )


def test_exact_fresh_boundary_is_fresh():

    evaluator = make_evaluator(
        fresh_for_ms=60000.0,

        usable_for_ms=300000.0,
    )

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            - timedelta(
                seconds=60,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .FRESH
    )


def test_value_immediately_beyond_fresh_boundary_is_stale():

    evaluator = make_evaluator(
        fresh_for_ms=60000.0,

        usable_for_ms=300000.0,
    )

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            - timedelta(
                milliseconds=60001,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .STALE
    )


def test_exact_usable_boundary_is_stale():

    evaluator = make_evaluator(
        fresh_for_ms=60000.0,

        usable_for_ms=300000.0,
    )

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            - timedelta(
                seconds=300,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .STALE
    )


def test_value_beyond_usable_boundary_is_unusable():

    evaluator = make_evaluator(
        fresh_for_ms=60000.0,

        usable_for_ms=300000.0,
    )

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            - timedelta(
                milliseconds=300001,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .UNUSABLE
    )

    assert (
        evaluation.reason

        == ResearchWorkspaceConsumerProjectionFreshnessReason
        .OUTSIDE_USABLE_WINDOW
    )


def test_zero_age_value_is_fresh():

    evaluator = make_evaluator()

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=_BASE_TIME,

        evaluated_at=_BASE_TIME,
    )

    assert evaluation.age_ms == 0.0

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .FRESH
    )


def test_small_allowed_future_skew_is_accepted():

    evaluator = make_evaluator(
        maximum_future_skew_ms=5000.0,
    )

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            + timedelta(
                seconds=2,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    assert evaluation.age_ms == 0.0

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .FRESH
    )


def test_excessive_future_timestamp_is_unusable():

    evaluator = make_evaluator(
        maximum_future_skew_ms=5000.0,
    )

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            + timedelta(
                minutes=10,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .UNUSABLE
    )

    assert (
        evaluation.reason

        == ResearchWorkspaceConsumerProjectionFreshnessReason
        .SOURCE_TIMESTAMP_IN_FUTURE
    )


def test_naive_source_timestamp_is_rejected():

    evaluator = make_evaluator()

    with pytest.raises(
        ValueError,
    ):

        evaluator.evaluate(

            source_name="test.source",

            source_timestamp=(
                datetime(
                    2026,

                    7,

                    14,
                )
            ),

            evaluated_at=_BASE_TIME,
        )


def test_freshness_policy_rejects_negative_fresh_window():

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name="x",

            fresh_for_ms=-1.0,

            usable_for_ms=100.0,
        )


def test_freshness_policy_rejects_negative_usable_window():

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name="x",

            fresh_for_ms=0.0,

            usable_for_ms=-1.0,
        )


def test_freshness_policy_rejects_usable_window_shorter_than_fresh_window():

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name="x",

            fresh_for_ms=300000.0,

            usable_for_ms=120000.0,
        )


def test_policy_registry_rejects_duplicate_source_names():

    policy_a = (

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name="workspace.integrity",

            fresh_for_ms=1000.0,

            usable_for_ms=2000.0,
        )
    )

    policy_b = (

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name="workspace.integrity",

            fresh_for_ms=5000.0,

            usable_for_ms=6000.0,
        )
    )

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry(
            policies=(
                policy_a,

                policy_b,
            ),
        )


def test_missing_policy_produces_configuration_error():

    evaluator = make_evaluator(
        source_name="known.source",
    )

    with pytest.raises(

        ResearchWorkspaceConsumerProjectionFreshnessPolicyNotFoundError,

    ):

        evaluator.evaluate(

            source_name="unknown.source",

            source_timestamp=_BASE_TIME,

            evaluated_at=_BASE_TIME,
        )


class CountingUtcClock:

    def __init__(

        self,

        value,

    ):

        self._value = value

        self.calls = 0

    def now(self):

        self.calls += 1

        return self._value


class CountingActivityService:

    def __init__(

        self,

        events,

    ):

        self._events = list(
            events
        )

        self.calls = 0

    def recent_activity(

        self,

        page=1,

        page_size=50,

    ):

        self.calls += 1

        return (

            ResearchActivityPage(
                items=(

                    self._events[
                        :page_size
                    ]
                ),

                page=page,

                page_size=page_size,

                total=len(
                    self._events
                ),
            )
        )


def make_activity_event(

    occurred_at,

    event_id="event-1",

):

    return (

        ResearchActivityEvent(

            id=event_id,

            activity_type=(

                ResearchActivityType
                .SESSION_CREATED
            ),

            occurred_at=occurred_at,

            actor_type=(

                ResearchActivityActorType
                .USER
            ),
        )
    )


def make_freshness_context(

    utc_clock,

    activity_events,

    diagnostics=None,

    fresh_for_ms=60000.0,

    usable_for_ms=300000.0,

):

    activity_service = (

        CountingActivityService(
            activity_events
        )
    )

    freshness_evaluator = (

        ResearchWorkspaceConsumerProjectionFreshnessEvaluator(

            policy_registry=(

                ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry(
                    policies=(

                        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

                            source_name=(
                                "workspace.recent_activity"
                            ),

                            fresh_for_ms=(
                                fresh_for_ms
                            ),

                            usable_for_ms=(
                                usable_for_ms
                            ),
                        ),
                    ),
                )
            ),
        )
    )

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

    context = (

        ResearchWorkspaceProjectionContext(

            capability_registry=stub,

            readiness_assessor=stub,

            integrity_auditor=stub,

            insights_service=stub,

            session_manager=stub,

            profile_store=stub,

            activity_service=(
                activity_service
            ),

            freshness_evaluator=(
                freshness_evaluator
            ),

            utc_clock=utc_clock,

            diagnostics=diagnostics,
        )
    )

    return context, activity_service


def test_execution_scope_captures_observation_time_once():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    context, _ = make_freshness_context(

        clock,

        [
            make_activity_event(
                _BASE_TIME
            ),
        ],
    )

    context.get_recent_activity_freshness()

    context.get_recent_activity_freshness()

    context.get_recent_activity_freshness()

    assert clock.calls == 1


def test_reused_input_does_not_reevaluate_freshness():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    context, activity_service = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    _BASE_TIME
                ),
            ],
        )
    )

    first = (
        context.get_recent_activity_freshness()
    )

    context.get_recent_activity_freshness()

    context.get_recent_activity_freshness()

    assert activity_service.calls == 1

    assert (
        first.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .FRESH
    )


def test_stale_value_is_memoized_normally():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    stale_timestamp = (

        _BASE_TIME

        - timedelta(
            seconds=90,
        )
    )

    context, activity_service = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    stale_timestamp
                ),
            ],

            fresh_for_ms=60000.0,

            usable_for_ms=300000.0,
        )
    )

    first = (
        context.get_recent_activity_freshness()
    )

    second = (
        context.get_recent_activity_freshness()
    )

    assert (
        first.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .STALE
    )

    assert first is second

    assert activity_service.calls == 1


def test_unusable_value_is_memoized_as_resolution_record():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    old_timestamp = (

        _BASE_TIME

        - timedelta(
            hours=2,
        )
    )

    context, activity_service = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    old_timestamp
                ),
            ],

            fresh_for_ms=60000.0,

            usable_for_ms=300000.0,
        )
    )

    with pytest.raises(

        ResearchWorkspaceConsumerProjectionUnusableFreshnessError,

    ):

        context.get_recent_activity_freshness()

    assert activity_service.calls == 1

    with pytest.raises(

        ResearchWorkspaceConsumerProjectionUnusableFreshnessError,

    ):

        context.get_recent_activity_freshness()

    assert activity_service.calls == 1


def test_resolver_exception_can_still_retry():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    context, activity_service = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    _BASE_TIME
                ),
            ],
        )
    )

    call_count = {
        "count": 0,
    }

    original_recent_activity = (

        activity_service
        .recent_activity
    )

    def flaky_recent_activity(

        page=1,

        page_size=50,

    ):

        call_count[
            "count"
        ] += 1

        if (

            call_count[
                "count"
            ]

            == 1
        ):

            raise RuntimeError(
                "temporary failure"
            )

        return (
            original_recent_activity(

                page=page,

                page_size=page_size,
            )
        )

    activity_service.recent_activity = (
        flaky_recent_activity
    )

    with pytest.raises(
        RuntimeError,
    ):

        context.get_recent_activity_freshness()

    evaluation = (
        context.get_recent_activity_freshness()
    )

    assert (
        evaluation.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .FRESH
    )

    assert call_count[
        "count"
    ] == 2


def test_stale_input_resolution_still_counts_as_successful():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    collector = (

        ResearchWorkspaceConsumerProjectionDiagnosticsCollector(

            operation_name="test.op",

            clock=(
                ResearchWorkspaceMonotonicClock()
            ),
        )
    )

    stale_timestamp = (

        _BASE_TIME

        - timedelta(
            seconds=90,
        )
    )

    context, _ = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    stale_timestamp
                ),
            ],

            diagnostics=collector,

            fresh_for_ms=60000.0,

            usable_for_ms=300000.0,
        )
    )

    context.get_recent_activity_freshness()

    report = collector.finalize()

    input_entry = next(

        entry

        for entry

        in report.inputs

        if (

            entry.name

            == "workspace.recent_activity"
        )
    )

    assert (
        input_entry.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .SUCCEEDED
    )

    assert (
        input_entry.freshness.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .STALE
    )


def test_unusable_input_resolution_still_records_successful_source_retrieval():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    collector = (

        ResearchWorkspaceConsumerProjectionDiagnosticsCollector(

            operation_name="test.op",

            clock=(
                ResearchWorkspaceMonotonicClock()
            ),
        )
    )

    old_timestamp = (

        _BASE_TIME

        - timedelta(
            hours=2,
        )
    )

    context, _ = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    old_timestamp
                ),
            ],

            diagnostics=collector,

            fresh_for_ms=60000.0,

            usable_for_ms=300000.0,
        )
    )

    with pytest.raises(

        ResearchWorkspaceConsumerProjectionUnusableFreshnessError,

    ):

        context.get_recent_activity_freshness()

    report = collector.finalize()

    input_entry = next(

        entry

        for entry

        in report.inputs

        if (

            entry.name

            == "workspace.recent_activity"
        )
    )

    assert (
        input_entry.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .SUCCEEDED
    )

    assert (
        input_entry.freshness.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .UNUSABLE
    )


def test_inputs_without_freshness_semantics_still_work():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    context, _ = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    _BASE_TIME
                ),
            ],
        )
    )

    assert (

        context.get_capabilities()

        == []
    )


def test_freshness_diagnostic_is_recorded_once():

    clock = CountingUtcClock(
        _BASE_TIME
    )

    collector = (

        ResearchWorkspaceConsumerProjectionDiagnosticsCollector(

            operation_name="test.op",

            clock=(
                ResearchWorkspaceMonotonicClock()
            ),
        )
    )

    context, _ = (

        make_freshness_context(

            clock,

            [
                make_activity_event(
                    _BASE_TIME
                ),
            ],

            diagnostics=collector,
        )
    )

    context.get_recent_activity_freshness()

    context.get_recent_activity_freshness()

    report = collector.finalize()

    matching_inputs = [

        entry

        for entry

        in report.inputs

        if (

            entry.name

            == "workspace.recent_activity"
        )
    ]

    assert len(
        matching_inputs
    ) == 1


def test_stale_used_source_can_degrade_operation():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    tiny_policy = (

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name=(
                "workspace.recent_activity"
            ),

            fresh_for_ms=0.0,

            usable_for_ms=(

                60

                * 60

                * 1000
            ),
        )
    )

    application.research_workspace_consumer_projection_freshness_evaluator = (

        ResearchWorkspaceConsumerProjectionFreshnessEvaluator(

            policy_registry=(

                ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry(
                    policies=(
                        tiny_policy,
                    ),
                )
            ),
        )
    )

    application.research_workspace_projection_context_factory._freshness_evaluator = (

        application
        .research_workspace_consumer_projection_freshness_evaluator
    )

    import time

    time.sleep(
        0.01
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    assert result.projection is not None

    assert (
        result.diagnostics.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .DEGRADED
    )

    activity_stage = next(

        stage

        for stage

        in result.diagnostics.stages

        if (

            stage.name

            == "workspace.bootstrap.recent_activity"
        )
    )

    assert (
        activity_stage.reason_code

        == "stale_source_used"
    )


def test_fresh_source_does_not_degrade_operation():

    application = (
        PreReqAIApplication()
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


def test_unusable_optional_source_gracefully_degrades_bootstrap():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    zero_policy = (

        ResearchWorkspaceConsumerProjectionFreshnessPolicy(

            source_name=(
                "workspace.recent_activity"
            ),

            fresh_for_ms=0.0,

            usable_for_ms=0.0,
        )
    )

    application.research_workspace_consumer_projection_freshness_evaluator = (

        ResearchWorkspaceConsumerProjectionFreshnessEvaluator(

            policy_registry=(

                ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry(
                    policies=(
                        zero_policy,
                    ),
                )
            ),
        )
    )

    application.research_workspace_projection_context_factory._freshness_evaluator = (

        application
        .research_workspace_consumer_projection_freshness_evaluator
    )

    import time

    time.sleep(
        0.01
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    assert result.projection is not None

    assert (
        result.projection.recent_activity

        == []
    )

    assert (
        result.diagnostics.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .DEGRADED
    )


def test_budget_skipped_stage_does_not_resolve_freshness_sensitive_source():

    from backend.session import (
        ResearchWorkspaceConsumerProjectionExecutionPolicy,
        ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry,
        ResearchWorkspaceConsumerProjectionStageBudgetPolicy,
        ResearchWorkspaceConsumerProjectionStageRequirement,
    )

    application = (
        PreReqAIApplication()
    )

    tiny_policy = (

        ResearchWorkspaceConsumerProjectionExecutionPolicy(

            operation_name=(
                "workspace.bootstrap"
            ),

            soft_budget_ms=0.0,

            stage_policies=[

                ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                    stage_name=(
                        "workspace.bootstrap.overview"
                    ),

                    requirement=(

                        ResearchWorkspaceConsumerProjectionStageRequirement
                        .MANDATORY
                    ),
                ),

                ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                    stage_name=(
                        "workspace.bootstrap.recent_activity"
                    ),

                    requirement=(

                        ResearchWorkspaceConsumerProjectionStageRequirement
                        .OPTIONAL
                    ),

                    minimum_remaining_budget_ms=(
                        10.0
                    ),
                ),

                ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                    stage_name=(
                        "workspace.bootstrap.assemble"
                    ),

                    requirement=(

                        ResearchWorkspaceConsumerProjectionStageRequirement
                        .MANDATORY
                    ),
                ),
            ],
        )
    )

    application.research_workspace.execution_policy_registry = (

        ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry(
            policies=(
                tiny_policy,
            ),
        )
    )

    original_recent_activity = (

        application
        .research_activity_service
        .recent_activity
    )

    calls = {
        "count": 0,
    }

    def counting_recent_activity(

        page=1,

        page_size=50,

    ):

        calls[
            "count"
        ] += 1

        return original_recent_activity(

            page=page,

            page_size=page_size,
        )

    application.research_activity_service.recent_activity = (
        counting_recent_activity
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    assert calls[
        "count"
    ] == 0

    freshness_input = [

        entry

        for entry

        in result.diagnostics.inputs

        if (

            entry.name

            == "workspace.recent_activity"
        )
    ]

    assert freshness_input == []


def test_budget_admitted_stage_evaluates_freshness_normally():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    activity_admission = next(

        admission

        for admission

        in result.diagnostics.budget_decisions

        if (

            admission.stage_name

            == "workspace.bootstrap.recent_activity"
        )
    )

    assert (

        activity_admission.decision.value

        == "execute"
    )

    freshness_input = next(

        entry

        for entry

        in result.diagnostics.inputs

        if (

            entry.name

            == "workspace.recent_activity"
        )
    )

    assert freshness_input.freshness is not None


def test_projection_context_reuse_remains_correct():

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

    application.research_workspace.diagnose_bootstrap()

    assert calls[
        "count"
    ] == 1


def test_separate_operations_reevaluate_freshness():

    stale_timestamp = (

        _BASE_TIME

        - timedelta(
            seconds=90,
        )
    )

    evaluator = make_evaluator(

        fresh_for_ms=60000.0,

        usable_for_ms=300000.0,

        source_name="workspace.recent_activity",
    )

    operation_a_time = _BASE_TIME

    operation_b_time = (

        _BASE_TIME

        + timedelta(
            minutes=10,
        )
    )

    evaluation_a = (

        evaluator.evaluate(

            source_name=(
                "workspace.recent_activity"
            ),

            source_timestamp=(
                stale_timestamp
            ),

            evaluated_at=(
                operation_a_time
            ),
        )
    )

    evaluation_b = (

        evaluator.evaluate(

            source_name=(
                "workspace.recent_activity"
            ),

            source_timestamp=(
                stale_timestamp
            ),

            evaluated_at=(
                operation_b_time
            ),
        )
    )

    assert (
        evaluation_a.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .STALE
    )

    assert (
        evaluation_b.status

        == ResearchWorkspaceConsumerProjectionFreshnessStatus
        .UNUSABLE
    )


def test_separate_operations_do_not_share_freshness_resolution_state():

    application = (
        PreReqAIApplication()
    )

    result_a = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    result_b = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    assert (

        result_a.diagnostics

        is not result_b.diagnostics
    )


def test_normal_bootstrap_payload_does_not_expose_freshness_internals():

    application = (
        PreReqAIApplication()
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    payload = projection.to_dict()

    serialized = str(
        payload
    )

    assert (
        "freshness_status"

        not in serialized
    )

    assert (
        "fresh_for_ms"

        not in serialized
    )

    assert (
        "usable_for_ms"

        not in serialized
    )


def test_freshness_policy_changes_do_not_change_consumer_contract_version():

    application = (
        PreReqAIApplication()
    )

    descriptor_before = (

        application
        .research_workspace
        .get_consumer_contract(
            "workspace.bootstrap"
        )
    )

    original_version = (

        (

            descriptor_before.version.major,

            descriptor_before.version.minor,
        )
    )

    application.research_workspace_consumer_projection_freshness_policy_registry = (

        ResearchWorkspaceConsumerProjectionFreshnessPolicyRegistry(
            policies=(

                ResearchWorkspaceConsumerProjectionFreshnessPolicy(

                    source_name=(
                        "workspace.recent_activity"
                    ),

                    fresh_for_ms=1000.0,

                    usable_for_ms=(

                        20

                        * 60

                        * 1000
                    ),
                ),
            ),
        )
    )

    descriptor_after = (

        application
        .research_workspace
        .get_consumer_contract(
            "workspace.bootstrap"
        )
    )

    assert (

        (

            descriptor_after.version.major,

            descriptor_after.version.minor,
        )

        == original_version
    )


def test_static_contract_manifest_does_not_require_freshness_evaluation():

    application = (
        PreReqAIApplication()
    )

    original_evaluate = (

        application
        .research_workspace_consumer_projection_freshness_evaluator
        .evaluate
    )

    calls = {
        "count": 0,
    }

    def counting_evaluate(
        **kwargs,
    ):

        calls[
            "count"
        ] += 1

        return original_evaluate(
            **kwargs
        )

    application.research_workspace_consumer_projection_freshness_evaluator.evaluate = (
        counting_evaluate
    )

    application.research_workspace.get_consumer_contract_manifest()

    assert calls[
        "count"
    ] == 0


def test_freshness_serialization_uses_primitive_values():

    evaluator = make_evaluator()

    evaluation = evaluator.evaluate(

        source_name="test.source",

        source_timestamp=(

            _BASE_TIME

            - timedelta(
                seconds=10,
            )
        ),

        evaluated_at=_BASE_TIME,
    )

    payload = evaluation.to_dict()

    assert payload["status"] == "fresh"

    assert (
        payload["reason"]

        == "within_fresh_window"
    )

    assert isinstance(
        payload["source_timestamp"],
        str,
    )

    assert isinstance(
        payload["evaluated_at"],
        str,
    )
