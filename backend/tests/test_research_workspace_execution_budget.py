import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionBudgetDecision,
    ResearchWorkspaceConsumerProjectionBudgetDecisionReason,
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
    ResearchWorkspaceConsumerProjectionDiagnosticsCollector,
    ResearchWorkspaceConsumerProjectionExecutionBudget,
    ResearchWorkspaceConsumerProjectionExecutionCoordinator,
    ResearchWorkspaceConsumerProjectionExecutionPolicy,
    ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry,
    ResearchWorkspaceConsumerProjectionStageBudgetPolicy,
    ResearchWorkspaceConsumerProjectionStageRequirement,
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


def create_budget(

    steps,

    soft_budget_ms=500.0,

    stage_policies=(),

):

    policy = (

        ResearchWorkspaceConsumerProjectionExecutionPolicy(

            operation_name="test.op",

            soft_budget_ms=(
                soft_budget_ms
            ),

            stage_policies=list(
                stage_policies
            ),
        )
    )

    return (

        ResearchWorkspaceConsumerProjectionExecutionBudget(

            policy=policy,

            clock=FakeClock(
                steps
            ),
        )
    )


def test_budget_starts_with_full_remaining_allowance():

    budget = create_budget(
        [0.0]
    )

    snapshot = budget.snapshot()

    assert snapshot.elapsed_ms == 0.0

    assert snapshot.remaining_ms == 500.0

    assert snapshot.overrun_ms == 0.0

    assert snapshot.exhausted is False


def test_budget_elapsed_time_uses_monotonic_clock():

    budget = create_budget(
        [0.0, 0.25]
    )

    snapshot = budget.snapshot()

    assert snapshot.elapsed_ms == 250.0


def test_remaining_budget_decreases():

    budget = create_budget(
        [0.0, 0.12]
    )

    snapshot = budget.snapshot()

    assert snapshot.remaining_ms == 380.0


def test_remaining_budget_is_clamped_to_zero():

    budget = create_budget(
        [0.0, 0.62]
    )

    snapshot = budget.snapshot()

    assert snapshot.remaining_ms == 0.0


def test_overrun_is_reported():

    budget = create_budget(
        [0.0, 0.62]
    )

    snapshot = budget.snapshot()

    assert snapshot.overrun_ms == 120.0


def test_unbounded_budget_never_exhausts():

    budget = create_budget(

        [0.0, 999.0],

        soft_budget_ms=None,
    )

    snapshot = budget.snapshot()

    assert snapshot.remaining_ms is None

    assert snapshot.overrun_ms == 0.0

    assert snapshot.exhausted is False


def test_mandatory_stage_is_always_admitted():

    budget = create_budget(
        [0.0, 0.62]
    )

    admission = budget.evaluate(

        stage_name="x",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .MANDATORY
        ),

        minimum_remaining_budget_ms=0.0,
    )

    assert (
        admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .EXECUTE
    )

    assert (
        admission.reason

        == ResearchWorkspaceConsumerProjectionBudgetDecisionReason
        .MANDATORY
    )


def test_optional_stage_executes_with_sufficient_remaining_budget():

    budget = create_budget(
        [0.0, 0.3]
    )

    admission = budget.evaluate(

        stage_name="x",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .OPTIONAL
        ),

        minimum_remaining_budget_ms=100.0,
    )

    assert (
        admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .EXECUTE
    )


def test_optional_stage_skips_below_threshold():

    budget = create_budget(
        [0.0, 0.42]
    )

    admission = budget.evaluate(

        stage_name="x",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .OPTIONAL
        ),

        minimum_remaining_budget_ms=100.0,
    )

    assert (
        admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .SKIP
    )

    assert (
        admission.reason

        == ResearchWorkspaceConsumerProjectionBudgetDecisionReason
        .INSUFFICIENT_REMAINING_BUDGET
    )


def test_optional_stage_skips_when_budget_exhausted():

    budget = create_budget(
        [0.0, 0.62]
    )

    admission = budget.evaluate(

        stage_name="x",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .OPTIONAL
        ),

        minimum_remaining_budget_ms=10.0,
    )

    assert (
        admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .SKIP
    )

    assert (
        admission.reason

        == ResearchWorkspaceConsumerProjectionBudgetDecisionReason
        .BUDGET_EXHAUSTED
    )


def test_optional_stage_executes_when_remaining_equals_threshold():

    budget = create_budget(
        [0.0, 0.4]
    )

    admission = budget.evaluate(

        stage_name="x",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .OPTIONAL
        ),

        minimum_remaining_budget_ms=100.0,
    )

    assert admission.remaining_ms == 100.0

    assert (
        admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .EXECUTE
    )


def test_unbounded_policy_admits_optional_stages():

    budget = create_budget(

        [0.0, 999.0],

        soft_budget_ms=None,
    )

    admission = budget.evaluate(

        stage_name="x",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .OPTIONAL
        ),

        minimum_remaining_budget_ms=100000.0,
    )

    assert (
        admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .EXECUTE
    )


def test_policy_rejects_duplicate_stage_names():

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionExecutionPolicy(

            operation_name="dup.op",

            soft_budget_ms=500.0,

            stage_policies=[

                ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                    stage_name="a",

                    requirement=(

                        ResearchWorkspaceConsumerProjectionStageRequirement
                        .OPTIONAL
                    ),
                ),

                ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                    stage_name="a",

                    requirement=(

                        ResearchWorkspaceConsumerProjectionStageRequirement
                        .MANDATORY
                    ),
                ),
            ],
        )


def test_policy_rejects_negative_budget():

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionExecutionPolicy(

            operation_name="neg.op",

            soft_budget_ms=-1.0,
        )


def test_policy_rejects_negative_admission_threshold():

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

            stage_name="a",

            requirement=(

                ResearchWorkspaceConsumerProjectionStageRequirement
                .OPTIONAL
            ),

            minimum_remaining_budget_ms=-10.0,
        )


def test_policy_registry_rejects_duplicate_operation_names():

    policy_a = (

        ResearchWorkspaceConsumerProjectionExecutionPolicy(

            operation_name=(
                "workspace.bootstrap"
            ),

            soft_budget_ms=500.0,
        )
    )

    policy_b = (

        ResearchWorkspaceConsumerProjectionExecutionPolicy(

            operation_name=(
                "workspace.bootstrap"
            ),

            soft_budget_ms=700.0,
        )
    )

    with pytest.raises(
        ValueError,
    ):

        ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry(

            policies=(
                policy_a,

                policy_b,
            ),
        )


def test_same_stage_can_have_different_requirements_across_operations():

    registry = (

        ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry()
    )

    bootstrap_policy = (

        registry.get_policy(
            "workspace.bootstrap"
        )
    )

    attention_policy = (

        registry.get_policy(
            "workspace.attention"
        )
    )

    bootstrap_stage = (

        bootstrap_policy
        .get_stage_policy(
            "workspace.attention.project"
        )
    )

    attention_stage = (

        attention_policy
        .get_stage_policy(
            "workspace.attention.project"
        )
    )

    assert (
        bootstrap_stage.requirement

        == ResearchWorkspaceConsumerProjectionStageRequirement
        .OPTIONAL
    )

    assert (
        attention_stage.requirement

        == ResearchWorkspaceConsumerProjectionStageRequirement
        .MANDATORY
    )


def test_admission_is_evaluated_immediately_before_execution():

    budget = create_budget(

        [
            0.0,

            0.05,

            0.45,
        ],
    )

    first = budget.evaluate(

        stage_name="a",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .OPTIONAL
        ),

        minimum_remaining_budget_ms=100.0,
    )

    second = budget.evaluate(

        stage_name="b",

        requirement=(

            ResearchWorkspaceConsumerProjectionStageRequirement
            .OPTIONAL
        ),

        minimum_remaining_budget_ms=100.0,
    )

    assert (
        first.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .EXECUTE
    )

    assert (
        second.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .SKIP
    )


def test_skipped_optional_stage_is_not_invoked():

    budget = create_budget(

        [0.0, 0.62],

        stage_policies=[

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "optional.stage"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .OPTIONAL
                ),

                minimum_remaining_budget_ms=(
                    10.0
                ),
            ),
        ],
    )

    coordinator = (

        ResearchWorkspaceConsumerProjectionExecutionCoordinator(
            budget=budget,
        )
    )

    calls = {
        "count": 0,
    }

    def operation():

        calls[
            "count"
        ] += 1

        return "value"

    result = (

        coordinator.execute_stage(

            name="optional.stage",

            operation=operation,
        )
    )

    assert calls[
        "count"
    ] == 0

    assert result is None


def test_admitted_stage_is_invoked_exactly_once():

    budget = create_budget(
        [0.0, 0.1]
    )

    coordinator = (

        ResearchWorkspaceConsumerProjectionExecutionCoordinator(
            budget=budget,
        )
    )

    calls = {
        "count": 0,
    }

    def operation():

        calls[
            "count"
        ] += 1

        return "value"

    result = (

        coordinator.execute_stage(

            name="mandatory.stage",

            operation=operation,
        )
    )

    assert calls[
        "count"
    ] == 1

    assert result == "value"


def test_mandatory_stage_executes_after_budget_exhaustion():

    budget = create_budget(
        [0.0, 0.9]
    )

    coordinator = (

        ResearchWorkspaceConsumerProjectionExecutionCoordinator(
            budget=budget,
        )
    )

    result = (

        coordinator.execute_stage(

            name="mandatory.stage",

            operation=(
                lambda: "assembled"
            ),
        )
    )

    assert result == "assembled"


def test_budget_does_not_interrupt_running_stage():

    stage_policies = [

        ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

            stage_name="slow.optional",

            requirement=(

                ResearchWorkspaceConsumerProjectionStageRequirement
                .OPTIONAL
            ),

            minimum_remaining_budget_ms=10.0,
        ),

        ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

            stage_name="next.optional",

            requirement=(

                ResearchWorkspaceConsumerProjectionStageRequirement
                .OPTIONAL
            ),

            minimum_remaining_budget_ms=10.0,
        ),
    ]

    budget = create_budget(

        [

            0.0,

            0.1,

            0.9,
        ],

        stage_policies=(
            stage_policies
        ),
    )

    policy = budget.policy

    coordinator = (

        ResearchWorkspaceConsumerProjectionExecutionCoordinator(
            budget=budget,
        )
    )

    slow_stage_policy = (

        policy.get_stage_policy(
            "slow.optional"
        )
    )

    slow_result = (

        coordinator.execute_stage(

            name="slow.optional",

            operation=(
                lambda: "slow-completed"
            ),
        )
    )

    assert (
        slow_result

        == "slow-completed"
    )

    next_result = (

        coordinator.execute_stage(

            name="next.optional",

            operation=(
                lambda: "should-not-run"
            ),

            on_skip=(
                lambda: "skipped"
            ),
        )
    )

    assert next_result == "skipped"

    assert (
        slow_stage_policy
        is not None
    )


def test_budget_decision_is_recorded_in_diagnostics():

    application = (
        PreReqAIApplication()
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    assert len(

        result
        .diagnostics
        .budget_decisions

    ) > 0

    decision = (

        result
        .diagnostics
        .budget_decisions[0]
    )

    assert decision.stage_name

    assert decision.decision is not None

    assert decision.reason is not None

    assert (
        decision.remaining_ms

        is not None
    )

    assert (
        decision.minimum_remaining_budget_ms

        is not None
    )


def test_skipped_stage_does_not_produce_failed_stage_diagnostic():

    from backend.session import (
        ResearchWorkspaceConsumerProjectionExecutionPolicy as Policy,
        ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry as PolicyRegistry,
        ResearchWorkspaceConsumerProjectionStageBudgetPolicy as StagePolicy,
    )

    application = (
        PreReqAIApplication()
    )

    tiny_policy = Policy(

        operation_name=(
            "workspace.bootstrap"
        ),

        soft_budget_ms=0.0,

        stage_policies=[

            StagePolicy(

                stage_name=(
                    "workspace.bootstrap.overview"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .MANDATORY
                ),
            ),

            StagePolicy(

                stage_name=(
                    "workspace.attention.project"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .OPTIONAL
                ),

                minimum_remaining_budget_ms=(
                    10.0
                ),
            ),

            StagePolicy(

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

    application.research_workspace.execution_policy_registry = (

        PolicyRegistry(
            policies=(
                tiny_policy,
            ),
        )
    )

    result = (

        application
        .research_workspace
        .diagnose_bootstrap()
    )

    attention_stage_diagnostics = [

        stage

        for stage

        in result.diagnostics.stages

        if (

            stage.name

            == "workspace.attention.project"
        )
    ]

    assert attention_stage_diagnostics == []

    skipped_admission = next(

        admission

        for admission

        in result.diagnostics.budget_decisions

        if (

            admission.stage_name

            == "workspace.attention.project"
        )
    )

    assert (
        skipped_admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .SKIP
    )


def test_executed_stage_still_produces_normal_stage_diagnostic():

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


def test_admitted_stage_failure_remains_a_failure():

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

    attention_admission = next(

        admission

        for admission

        in result.diagnostics.budget_decisions

        if (

            admission.stage_name

            == "workspace.attention.project"
        )
    )

    assert (
        attention_admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .EXECUTE
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


def test_budget_skipped_optional_bootstrap_stage_produces_degraded_projection():

    from backend.session import (
        ResearchWorkspaceConsumerProjectionExecutionPolicy as Policy,
        ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry as PolicyRegistry,
        ResearchWorkspaceConsumerProjectionStageBudgetPolicy as StagePolicy,
    )

    application = (
        PreReqAIApplication()
    )

    tiny_policy = Policy(

        operation_name=(
            "workspace.bootstrap"
        ),

        soft_budget_ms=0.0,

        stage_policies=[

            StagePolicy(

                stage_name=(
                    "workspace.bootstrap.overview"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .MANDATORY
                ),
            ),

            StagePolicy(

                stage_name=(
                    "workspace.attention.project"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .OPTIONAL
                ),

                minimum_remaining_budget_ms=(
                    10.0
                ),
            ),

            StagePolicy(

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

    application.research_workspace.execution_policy_registry = (

        PolicyRegistry(
            policies=(
                tiny_policy,
            ),
        )
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


def test_all_bootstrap_stages_within_budget_produce_full_success():

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

    assert all(

        admission.decision

        == ResearchWorkspaceConsumerProjectionBudgetDecision
        .EXECUTE

        for admission

        in result.diagnostics.budget_decisions
    )


def test_budget_exhaustion_alone_does_not_mean_failure():

    collector = (

        ResearchWorkspaceConsumerProjectionDiagnosticsCollector(

            operation_name="test.op",

            clock=FakeClock(
                [0.0, 0.01]
            ),
        )
    )

    report = collector.finalize()

    assert (
        report.status

        == ResearchWorkspaceConsumerProjectionDiagnosticStatus
        .SUCCEEDED
    )


def test_budget_overrun_is_reported_separately():

    budget = create_budget(
        [0.0, 0.62]
    )

    snapshot = budget.snapshot()

    assert snapshot.overrun_ms == 120.0

    coordinator = (

        ResearchWorkspaceConsumerProjectionExecutionCoordinator(
            budget=budget,
        )
    )

    result = (

        coordinator.execute_stage(

            name="mandatory",

            operation=(
                lambda: "ok"
            ),
        )
    )

    assert result == "ok"


def test_projection_context_reuse_still_works_under_budgeting():

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

    application.research_workspace.get_bootstrap()

    assert calls[
        "count"
    ] == 1


def test_diagnostics_still_record_input_reuse():

    application = (
        PreReqAIApplication()
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

    assert readiness_input.reuse_count > 0


def test_separate_operations_have_separate_budgets():

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

    overview_a = next(

        admission

        for admission

        in result_a.diagnostics.budget_decisions

        if (

            admission.stage_name

            == "workspace.bootstrap.overview"
        )
    )

    overview_b = next(

        admission

        for admission

        in result_b.diagnostics.budget_decisions

        if (

            admission.stage_name

            == "workspace.bootstrap.overview"
        )
    )

    assert overview_a.elapsed_ms >= 0

    assert overview_b.elapsed_ms >= 0

    assert (
        overview_a.elapsed_ms

        < 400.0
    )

    assert (
        overview_b.elapsed_ms

        < 400.0
    )


def test_separate_operations_have_separate_diagnostics():

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

    assert (

        len(
            result_a.diagnostics.budget_decisions
        )

        == len(
            result_b.diagnostics.budget_decisions
        )
    )


def test_static_contract_manifest_does_not_require_execution_budget():

    application = (
        PreReqAIApplication()
    )

    original_create = (

        application
        .research_workspace_consumer_projection_execution_budget_factory
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

    application.research_workspace_consumer_projection_execution_budget_factory.create = (
        counting_create
    )

    application.research_workspace.get_consumer_contract_manifest()

    assert calls[
        "count"
    ] == 0


def test_execution_policy_does_not_change_consumer_contract_version():

    application = (
        PreReqAIApplication()
    )

    descriptor = (

        application
        .research_workspace
        .get_consumer_contract(
            "workspace.bootstrap"
        )
    )

    original_version = (

        (

            descriptor.version.major,

            descriptor.version.minor,
        )
    )

    application.research_workspace_consumer_projection_execution_policy_registry = (

        ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry(

            policies=(

                ResearchWorkspaceConsumerProjectionExecutionPolicy(

                    operation_name=(
                        "workspace.bootstrap"
                    ),

                    soft_budget_ms=700.0,
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


def test_normal_consumer_payload_does_not_expose_internal_budget_metadata():

    application = (
        PreReqAIApplication()
    )

    projection = (

        application
        .research_workspace
        .get_bootstrap()
    )

    payload = projection.to_dict()

    serialized_keys = str(
        payload.keys()
    )

    assert (
        "soft_budget_ms"

        not in serialized_keys
    )

    assert (
        "budget_decisions"

        not in serialized_keys
    )


def test_diagnostic_serialization_uses_primitive_values():

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

    for admission in (
        payload["budget_decisions"]
    ):

        assert isinstance(
            admission["decision"],
            str,
        )

        assert isinstance(
            admission["reason"],
            str,
        )

        assert isinstance(
            admission["requirement"],
            str,
        )
