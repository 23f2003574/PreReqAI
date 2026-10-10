import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_baselines import (
    ACTIVE,
    SUPERSEDED,
    DuplicateBaselineError,
    IncompleteEvaluationRunError,
    LLMEvaluationBaselineService,
    RegressedBaselineRunError,
    ThresholdFailureError,
    UnknownEvaluationBaselineError,
)
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_comparison import LLMEvaluationComparisonService
from backend.llm.evaluation_criteria import LLMEvaluationCriteriaService, LLMEvaluationCriterion
from backend.llm.evaluation_dataset_runs import LLMEvaluationDatasetRunService
from backend.llm.evaluation_datasets import LLMEvaluationDatasetService
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

    return {
        "case": case_service,
        "run": run_service,
        "criteria": criteria_service,
        "scoring": scoring_service,
        "threshold": threshold_service,
        "dataset": dataset_service,
        "dataset_run": dataset_run_service,
        "baseline": baseline_service,
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
    dataset = env["dataset"].create("notebook benchmark", "notebook_analysis", [case_id])
    return dataset


def test_accept_valid_run():
    env = build_env([make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    baseline = env["baseline"].accept(dataset_run.dataset_run_id)

    assert baseline.dataset_id == dataset.dataset_id
    assert baseline.run_id == dataset_run.dataset_run_id
    assert baseline.provider == "openai"
    assert baseline.model == "gpt-4o"
    assert baseline.overall_score == 1.0
    assert baseline.status == ACTIVE
    assert env["baseline"].get(dataset.dataset_id) is baseline


def test_threshold_failure():
    env = build_env([make_response(THREE_QUARTER_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.9)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")

    with pytest.raises(ThresholdFailureError):
        env["baseline"].validate(dataset_run.dataset_run_id)

    with pytest.raises(ThresholdFailureError):
        env["baseline"].accept(dataset_run.dataset_run_id)


def test_regression_rejection():
    env = build_env([make_response(FULL_MATCH), make_response(ZERO_MATCH)])
    dataset = setup_single_case_dataset(env)

    baseline_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    env["baseline"].accept(baseline_run.dataset_run_id)

    candidate_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o-mini")

    with pytest.raises(RegressedBaselineRunError):
        env["baseline"].validate(candidate_run.dataset_run_id)

    with pytest.raises(RegressedBaselineRunError):
        env["baseline"].replace(dataset.dataset_id, candidate_run.dataset_run_id)

    # The original baseline is untouched by the rejected attempt.
    assert env["baseline"].get(dataset.dataset_id).run_id == baseline_run.dataset_run_id


def test_duplicate_baseline():
    env = build_env([make_response(FULL_MATCH), make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)

    first_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    env["baseline"].accept(first_run.dataset_run_id)

    second_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")

    with pytest.raises(DuplicateBaselineError):
        env["baseline"].accept(second_run.dataset_run_id)


def test_replacement_and_history():
    env = build_env([make_response(FULL_MATCH), make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)

    first_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    original = env["baseline"].accept(first_run.dataset_run_id)
    assert original.status == ACTIVE

    second_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    replacement = env["baseline"].replace(dataset.dataset_id, second_run.dataset_run_id)

    assert replacement.status == ACTIVE
    assert replacement.run_id == second_run.dataset_run_id
    assert original.status == SUPERSEDED
    assert env["baseline"].get(dataset.dataset_id) is replacement

    with pytest.raises(UnknownEvaluationBaselineError):
        env["baseline"].replace("does-not-exist", second_run.dataset_run_id)


def test_invalid_run():
    env = build_env([RuntimeError("provider exploded")])
    dataset = setup_single_case_dataset(env)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")

    with pytest.raises(IncompleteEvaluationRunError):
        env["baseline"].validate(dataset_run.dataset_run_id)

    with pytest.raises(IncompleteEvaluationRunError):
        env["baseline"].accept(dataset_run.dataset_run_id)


def test_dataset_isolation():
    env = build_env([make_response(FULL_MATCH), make_response(THREE_QUARTER_MATCH)])

    env["case"].register(make_case("case-a", task_type="notebook_analysis"))
    env["case"].register(
        make_case(
            "case-b",
            task_type="notebook_analysis",
            expected_properties={"a": ["x"], "b": ["y"]},
        )
    )
    env["criteria"].register(make_criterion())

    dataset_a = env["dataset"].create("dataset a", "notebook_analysis", ["case-a"])
    dataset_b = env["dataset"].create("dataset b", "notebook_analysis", ["case-b"])

    run_a = env["dataset_run"].run(dataset_a.dataset_id, provider="openai", model="gpt-4o")
    run_b = env["dataset_run"].run(dataset_b.dataset_id, provider="openai", model="gpt-4o")

    baseline_a = env["baseline"].accept(run_a.dataset_run_id)
    baseline_b = env["baseline"].accept(run_b.dataset_run_id)

    assert baseline_a.dataset_id == dataset_a.dataset_id
    assert baseline_b.dataset_id == dataset_b.dataset_id
    assert env["baseline"].get(dataset_a.dataset_id) is baseline_a
    assert env["baseline"].get(dataset_b.dataset_id) is baseline_b
    assert env["baseline"].get(dataset_a.dataset_id) is not env["baseline"].get(dataset_b.dataset_id)

    with pytest.raises(UnknownEvaluationBaselineError):
        env["baseline"].get("does-not-exist")
