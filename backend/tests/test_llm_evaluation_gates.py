import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_baselines import LLMEvaluationBaselineService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_comparison import LLMEvaluationComparisonService
from backend.llm.evaluation_criteria import LLMEvaluationCriteriaService, LLMEvaluationCriterion
from backend.llm.evaluation_dataset_runs import LLMEvaluationDatasetRunService
from backend.llm.evaluation_datasets import LLMEvaluationDatasetService
from backend.llm.evaluation_gates import ACCEPTED, REJECTED, LLMEvaluationGateService
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


def finding(gate, check):
    return next(f for f in gate.findings if f["check"] == check)


def test_all_checks_pass():
    env = build_env([make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    gate = env["gate"].evaluate(dataset_run.dataset_run_id)

    assert gate.status == ACCEPTED
    assert all(f["passed"] for f in gate.findings)
    assert finding(gate, "baseline_regression")["detail"].startswith("no active baseline")
    assert env["gate"].passed(dataset_run.dataset_run_id) is True


def test_threshold_failure():
    env = build_env([make_response(THREE_QUARTER_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.9)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    gate = env["gate"].evaluate(dataset_run.dataset_run_id)

    assert gate.status == REJECTED
    assert finding(gate, "thresholds_passed")["passed"] is False
    assert finding(gate, "completed_run")["passed"] is True


def test_baseline_regression():
    env = build_env([make_response(FULL_MATCH), make_response(ZERO_MATCH)])
    dataset = setup_single_case_dataset(env)
    # A lenient threshold so only the regression check can fail.
    env["threshold"].set("criterion-imports-present", 0.0)

    baseline_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    env["baseline"].accept(baseline_run.dataset_run_id)

    candidate_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o-mini")
    gate = env["gate"].evaluate(candidate_run.dataset_run_id)

    assert gate.status == REJECTED
    assert finding(gate, "baseline_regression")["passed"] is False
    assert finding(gate, "thresholds_passed")["passed"] is True


def test_missing_baseline():
    env = build_env([make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    gate = env["gate"].evaluate(dataset_run.dataset_run_id)

    regression_finding = finding(gate, "baseline_regression")
    assert regression_finding["passed"] is True
    assert "no active baseline" in regression_finding["detail"]
    assert gate.status == ACCEPTED


def test_missing_criterion():
    env = build_env([make_response(FULL_MATCH)])
    env["case"].register(make_case("case-a"))
    env["criteria"].register(make_criterion(criterion_id="criterion-a", name="criterion a"))
    env["criteria"].register(
        make_criterion(criterion_id="criterion-b", name="criterion b", required=True)
    )
    dataset = env["dataset"].create("notebook benchmark", "notebook_analysis", ["case-a"])
    env["threshold"].set("criterion-a", 0.5)
    env["threshold"].set("criterion-b", 0.5)

    # criterion-b is disabled after its threshold was configured, so scoring
    # no longer covers it -- Commit #5's "missing required score" rule fires.
    env["criteria"].disable("criterion-b")

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    gate = env["gate"].evaluate(dataset_run.dataset_run_id)

    assert gate.status == REJECTED
    assert finding(gate, "thresholds_passed")["passed"] is False
    assert finding(gate, "thresholds_configured")["passed"] is True


def test_incomplete_run():
    env = build_env([RuntimeError("provider exploded")])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")
    gate = env["gate"].evaluate(dataset_run.dataset_run_id)

    assert gate.status == REJECTED
    assert finding(gate, "completed_run")["passed"] is False
    assert finding(gate, "thresholds_passed")["detail"].startswith("skipped")


def test_deterministic_gate_result():
    env = build_env([make_response(FULL_MATCH)])
    dataset = setup_single_case_dataset(env)
    env["threshold"].set("criterion-imports-present", 0.5)

    dataset_run = env["dataset_run"].run(dataset.dataset_id, provider="openai", model="gpt-4o")

    first = env["gate"].evaluate(dataset_run.dataset_run_id)
    second = env["gate"].evaluate(dataset_run.dataset_run_id)

    first_shape = [(f["check"], f["passed"]) for f in first.findings]
    second_shape = [(f["check"], f["passed"]) for f in second.findings]
    assert first.status == second.status == ACCEPTED
    assert first_shape == second_shape
