import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_baselines import LLMEvaluationBaselineService, UnknownEvaluationBaselineError
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_comparison import LLMEvaluationComparisonService
from backend.llm.evaluation_criteria import LLMEvaluationCriteriaService, LLMEvaluationCriterion
from backend.llm.evaluation_dataset_runs import LLMEvaluationDatasetRunService
from backend.llm.evaluation_datasets import LLMEvaluationDatasetService
from backend.llm.evaluation_gates import LLMEvaluationGateService
from backend.llm.evaluation_orchestration import (
    ACCEPTED,
    PASSED,
    REJECTED,
    GateNotPassedError,
    LLMEvaluationOrchestrationService,
    UnknownEvaluationDecisionError,
)
from backend.llm.evaluation_regressions import LLMEvaluationRegressionService
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
    dataset_service = LLMEvaluationDatasetService(case_service)
    dataset_run_service = LLMEvaluationDatasetRunService(dataset_service, run_service)
    baseline_service = LLMEvaluationBaselineService(
        dataset_run_service, scoring_service, threshold_service, regression_service
    )
    gate_service = LLMEvaluationGateService(
        dataset_run_service,
        dataset_service,
        criteria_service,
        threshold_service,
        regression_service,
        baseline_service,
    )
    eval_orchestration_service = LLMEvaluationOrchestrationService(
        dataset_run_service, scoring_service, gate_service, baseline_service, regression_service
    )

    return {
        "case": case_service,
        "run": run_service,
        "criteria": criteria_service,
        "scoring": scoring_service,
        "threshold": threshold_service,
        "dataset": dataset_service,
        "dataset_run": dataset_run_service,
        "baseline": baseline_service,
        "gate": gate_service,
        "orchestration": eval_orchestration_service,
    }


FULL_MATCH = '{"a": ["x"], "b": ["y"], "c": ["z"], "d": ["w"]}'
THREE_QUARTER_MATCH = '{"a": ["x"], "b": ["y"], "c": ["z"]}'
ZERO_MATCH = "{}"


def make_case(case_id, **overrides):
    fields = {
        "case_id": case_id,
        "name": f"case {case_id}",
        "task_type": "notebook_analysis",
        "input": {"notebook_id": case_id, "cells": [{"index": 0, "cell_type": "code", "source": "import pandas"}]},
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
        "required": True,
    }
    fields.update(overrides)
    return LLMEvaluationCriterion(**fields)


def setup_single_case_dataset(env, case_id="case-a"):
    env["case"].register(make_case(case_id))
    env["criteria"].register(make_criterion())
    return env["dataset"].create("notebook benchmark", "notebook_analysis", [case_id])


def test_successful_evaluation_and_acceptance():
    env = build_env([make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    decision = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")

    assert decision.status == PASSED
    assert decision.score == 1.0
    assert decision.blocking_findings == []
    assert decision.baseline_id is None
    assert decision.provider == "openai"
    assert decision.model == "gpt-4o"

    accepted = env["orchestration"].accept(decision.dataset_run_id)
    assert accepted.status == ACCEPTED
    assert accepted.baseline_id is not None
    assert env["baseline"].get(dataset.dataset_id).baseline_id == accepted.baseline_id


def test_threshold_failure():
    env = build_env([make_response(THREE_QUARTER_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.9)

    decision = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")

    assert decision.status == REJECTED
    assert any(f["check"] == "thresholds_passed" for f in decision.blocking_findings)

    with pytest.raises(GateNotPassedError):
        env["orchestration"].accept(decision.dataset_run_id)


def test_regression_rejection():
    env = build_env([make_response(FULL_MATCH), make_response(ZERO_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.0)

    baseline_decision = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")
    env["orchestration"].accept(baseline_decision.dataset_run_id)

    candidate_decision = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o-mini")

    assert candidate_decision.status == REJECTED
    assert any(f["check"] == "baseline_regression" for f in candidate_decision.blocking_findings)

    with pytest.raises(GateNotPassedError):
        env["orchestration"].accept(candidate_decision.dataset_run_id)

    # The active baseline is still the original, untouched by the rejection.
    assert env["baseline"].get(dataset.dataset_id).run_id == baseline_decision.dataset_run_id


def test_missing_baseline():
    env = build_env([make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    decision = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")

    assert decision.baseline_id is None
    assert decision.status == PASSED
    with pytest.raises(UnknownEvaluationBaselineError):
        env["baseline"].get(dataset.dataset_id)


def test_incomplete_dataset_run():
    env = build_env([RuntimeError("provider exploded")])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    decision = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")

    assert decision.status == REJECTED
    assert any(f["check"] == "completed_run" for f in decision.blocking_findings)
    assert decision.score is None


def test_gate_failure_without_configured_thresholds():
    env = build_env([make_response(FULL_MATCH)])
    env["case"].register(make_case("case-a"))
    env["criteria"].register(make_criterion())
    dataset = env["dataset"].create("notebook benchmark", "notebook_analysis", ["case-a"])
    # No threshold configured at all for this task_type.

    decision = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")

    assert decision.status == REJECTED
    assert any(f["check"] == "thresholds_configured" for f in decision.blocking_findings)
    assert decision.score == 1.0


def test_explicit_baseline_acceptance():
    env = build_env([make_response(FULL_MATCH), make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    first = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")
    with pytest.raises(UnknownEvaluationBaselineError):
        env["baseline"].get(dataset.dataset_id)

    second = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")
    with pytest.raises(UnknownEvaluationBaselineError):
        env["baseline"].get(dataset.dataset_id)

    accepted = env["orchestration"].accept(second.dataset_run_id)
    assert env["baseline"].get(dataset.dataset_id).run_id == second.dataset_run_id
    assert accepted.baseline_id == env["baseline"].get(dataset.dataset_id).baseline_id

    # The first evaluation was never promoted -- evaluate() alone never
    # silently replaces the active baseline.
    assert env["orchestration"].decision(first.dataset_run_id).status == PASSED


def test_deterministic_decision():
    env = build_env([make_response(FULL_MATCH), make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    first = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")
    second = env["orchestration"].evaluate(dataset.dataset_id, "openai", "gpt-4o")

    assert (first.status, first.score, first.blocking_findings) == (
        second.status,
        second.score,
        second.blocking_findings,
    )
    assert env["orchestration"].decision(first.dataset_run_id) is first
    assert env["orchestration"].decision(first.dataset_run_id).status == first.status

    with pytest.raises(UnknownEvaluationDecisionError):
        env["orchestration"].decision("does-not-exist")
