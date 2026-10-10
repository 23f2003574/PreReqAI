import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_comparison import (
    IncompatibleEvaluationCasesError,
    LLMEvaluationComparisonService,
)
from backend.llm.evaluation_criteria import LLMEvaluationCriteriaService, LLMEvaluationCriterion
from backend.llm.evaluation_regressions import (
    REGRESSED,
    SEVERITY_CRITICAL,
    SEVERITY_MINOR,
    SEVERITY_NONE,
    UNCHANGED,
    LLMEvaluationRegressionService,
)
from backend.llm.evaluation_runs import LLMEvaluationRunService
from backend.llm.evaluation_scoring import LLMEvaluationScoringService
from backend.llm.evaluation_thresholds import LLMEvaluationThresholdService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays a scripted outcome per call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


def build_env(script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": ScriptedProvider(script)},
    )

    case_service = LLMEvaluationCaseService()
    run_service = LLMEvaluationRunService(orchestration_service, context_service, case_service)
    criteria_service = LLMEvaluationCriteriaService()
    scoring_service = LLMEvaluationScoringService(run_service, case_service, criteria_service)
    threshold_service = LLMEvaluationThresholdService(criteria_service, scoring_service)
    comparison_service = LLMEvaluationComparisonService(run_service, case_service, scoring_service)
    regression_service = LLMEvaluationRegressionService(comparison_service, threshold_service)

    return (
        case_service,
        run_service,
        criteria_service,
        scoring_service,
        threshold_service,
        comparison_service,
        regression_service,
    )


FULL_MATCH = '{"a": ["x"], "b": ["y"], "c": ["z"], "d": ["w"]}'
THREE_QUARTER_MATCH = '{"a": ["x"], "b": ["y"], "c": ["z"]}'


def make_case(**overrides):
    fields = {
        "case_id": "case-notebook-analysis-1",
        "name": "notebook analysis extracts imports",
        "task_type": "notebook_analysis",
        "input": {"notebook_id": "nb-1", "cells": [{"index": 0, "cell_type": "code", "source": "import pandas"}]},
        "expected_properties": {"a": ["x"], "b": ["y"], "c": ["z"], "d": ["w"]},
    }
    fields.update(overrides)
    return LLMEvaluationCase(**fields)


def make_criterion(**overrides):
    fields = {
        "criterion_id": "criterion-imports-present",
        "name": "imports are present",
        "task_type": "notebook_analysis",
        "description": "the analysis must list every import statement found in the notebook",
        "weight": 1.0,
    }
    fields.update(overrides)
    return LLMEvaluationCriterion(**fields)


def test_no_regression():
    (case_service, run_service, criteria_service, scoring_service, threshold_service,
     comparison_service, regression_service) = build_env(
        [make_response(FULL_MATCH), make_response(FULL_MATCH)]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    results = regression_service.analyze(baseline.run_id, candidate.run_id)

    assert len(results) == 1
    assert results[0].delta == 0.0
    assert results[0].status == UNCHANGED
    assert results[0].severity == SEVERITY_NONE
    assert regression_service.regressions(candidate.run_id) == []
    assert regression_service.critical(candidate.run_id) == []


def test_criterion_regression():
    (case_service, run_service, criteria_service, scoring_service, threshold_service,
     comparison_service, regression_service) = build_env(
        [make_response(FULL_MATCH), make_response(THREE_QUARTER_MATCH)]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    results = regression_service.analyze(baseline.run_id, candidate.run_id)

    assert len(results) == 1
    assert results[0].delta == -0.25
    assert results[0].status == REGRESSED
    assert results[0].severity == SEVERITY_MINOR

    flagged = regression_service.regressions(candidate.run_id)
    assert len(flagged) == 1
    assert flagged[0].criterion == "criterion-imports-present"


def test_threshold_triggered_regression():
    (case_service, run_service, criteria_service, scoring_service, threshold_service,
     comparison_service, regression_service) = build_env(
        [make_response(FULL_MATCH), make_response(THREE_QUARTER_MATCH)]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())
    threshold_service.set("criterion-imports-present", 0.9)

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    results = regression_service.analyze(baseline.run_id, candidate.run_id)

    assert results[0].delta == -0.25
    assert results[0].status == REGRESSED
    # Same delta magnitude as test_criterion_regression, but the configured
    # threshold (0.9) is breached by the candidate's 0.75, so it escalates.
    assert results[0].severity == SEVERITY_CRITICAL
    assert len(regression_service.critical(candidate.run_id)) == 1


def test_missing_criterion_handled_gracefully():
    (case_service, run_service, criteria_service, scoring_service, threshold_service,
     comparison_service, regression_service) = build_env(
        [make_response(FULL_MATCH), make_response(FULL_MATCH)]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())
    criteria_service.register(
        make_criterion(criterion_id="criterion-disabled", name="disabled check")
    )
    criteria_service.disable("criterion-disabled")

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    results = regression_service.analyze(baseline.run_id, candidate.run_id)

    criteria_seen = {r.criterion for r in results}
    assert criteria_seen == {"criterion-imports-present"}
    assert "criterion-disabled" not in criteria_seen


def test_incompatible_datasets():
    (case_service, run_service, criteria_service, scoring_service, threshold_service,
     comparison_service, regression_service) = build_env(
        [make_response(FULL_MATCH), make_response('{"is_candidate": true}')]
    )
    case_service.register(make_case())
    case_service.register(
        make_case(
            case_id="case-api-candidate-1",
            name="api candidate detection finds a route",
            task_type="api_candidate_detection",
            input={"function_name": "get_user", "signature": "def get_user(id: int)"},
            expected_properties={"is_candidate": True},
        )
    )
    criteria_service.register(make_criterion())

    notebook_run = run_service.run("case-notebook-analysis-1")
    api_run = run_service.run("case-api-candidate-1")

    with pytest.raises(IncompatibleEvaluationCasesError):
        regression_service.analyze(notebook_run.run_id, api_run.run_id)


def test_critical_filtering():
    (case_service, run_service, criteria_service, scoring_service, threshold_service,
     comparison_service, regression_service) = build_env(
        [make_response(FULL_MATCH), make_response(THREE_QUARTER_MATCH)]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(criterion_id="criterion-a", name="criterion a"))
    criteria_service.register(make_criterion(criterion_id="criterion-b", name="criterion b"))
    threshold_service.set("criterion-a", 0.9)

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    regression_service.analyze(baseline.run_id, candidate.run_id)

    flagged = {r.criterion: r for r in regression_service.regressions(candidate.run_id)}
    assert set(flagged) == {"criterion-a", "criterion-b"}
    assert flagged["criterion-a"].severity == SEVERITY_CRITICAL
    assert flagged["criterion-b"].severity == SEVERITY_MINOR

    critical = regression_service.critical(candidate.run_id)
    assert [r.criterion for r in critical] == ["criterion-a"]


def test_deterministic_result():
    (case_service, run_service, criteria_service, scoring_service, threshold_service,
     comparison_service, regression_service) = build_env(
        [make_response(FULL_MATCH), make_response(THREE_QUARTER_MATCH)]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    first = regression_service.analyze(baseline.run_id, candidate.run_id)
    second = regression_service.analyze(baseline.run_id, candidate.run_id)

    first_shape = [(r.criterion, r.delta, r.status, r.severity) for r in first]
    second_shape = [(r.criterion, r.delta, r.status, r.severity) for r in second]
    assert first_shape == second_shape
