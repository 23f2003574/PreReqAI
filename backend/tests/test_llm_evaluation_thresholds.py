import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_criteria import (
    LLMEvaluationCriteriaService,
    LLMEvaluationCriterion,
    UnknownEvaluationCriterionError,
)
from backend.llm.evaluation_runs import LLMEvaluationRunService
from backend.llm.evaluation_scoring import LLMEvaluationScoringService
from backend.llm.evaluation_thresholds import (
    LLMEvaluationThresholdService,
    UnknownEvaluationThresholdError,
)
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

    return case_service, run_service, criteria_service, scoring_service, threshold_service


def make_case(**overrides):
    fields = {
        "case_id": "case-notebook-analysis-1",
        "name": "notebook analysis extracts imports",
        "task_type": "notebook_analysis",
        "input": {"notebook_id": "nb-1", "cells": [{"index": 0, "cell_type": "code", "source": "import pandas"}]},
        "expected_properties": {"imports": ["pandas"]},
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


def test_threshold_configuration():
    _, _, criteria_service, _, threshold_service = build_env([make_response("ok")])
    criteria_service.register(make_criterion())

    threshold = threshold_service.set("criterion-imports-present", 0.75)

    assert threshold.criterion_id == "criterion-imports-present"
    assert threshold.minimum_score == 0.75
    assert threshold.enabled is True
    assert threshold_service.get("criterion-imports-present") is threshold

    # set() again replaces the configured minimum_score for the same criterion.
    updated = threshold_service.set("criterion-imports-present", 0.9)
    assert updated.minimum_score == 0.9
    assert threshold_service.get("criterion-imports-present").minimum_score == 0.9

    with pytest.raises(UnknownEvaluationCriterionError):
        threshold_service.set("does-not-exist", 0.5)

    with pytest.raises(UnknownEvaluationThresholdError):
        threshold_service.get("does-not-exist")


def test_score_above_below_threshold():
    case_service, run_service, criteria_service, scoring_service, threshold_service = build_env(
        [make_response('{"imports": ["pandas"]}'), make_response('{"imports": []}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(required=False))
    threshold_service.set("criterion-imports-present", 0.5)

    passing_run = run_service.run("case-notebook-analysis-1")
    passing_result = threshold_service.evaluate(passing_run.run_id)[0]
    assert passing_result["score"] == 1.0
    assert passing_result["passed"] is True

    failing_run = run_service.run("case-notebook-analysis-1")
    failing_result = threshold_service.evaluate(failing_run.run_id)[0]
    assert failing_result["score"] == 0.0
    assert failing_result["passed"] is False


def test_missing_score():
    case_service, run_service, criteria_service, scoring_service, threshold_service = build_env(
        [make_response('{"imports": ["pandas"]}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(criterion_id="criterion-required", required=True))
    criteria_service.register(
        make_criterion(criterion_id="criterion-other", name="other check", required=False)
    )
    threshold_service.set("criterion-required", 0.5)
    threshold_service.set("criterion-other", 0.5)

    # Disabled after the threshold was set -- Commit #3 excludes it from scoring.
    criteria_service.disable("criterion-required")

    run = run_service.run("case-notebook-analysis-1")
    results = {r["criterion_id"]: r for r in threshold_service.evaluate(run.run_id)}

    assert results["criterion-required"]["score"] is None
    assert results["criterion-required"]["passed"] is False
    assert results["criterion-other"]["score"] == 1.0

    assert threshold_service.passed(run.run_id) is False
    assert any(f["criterion_id"] == "criterion-required" for f in threshold_service.failures(run.run_id))


def test_required_criterion_failure():
    case_service, run_service, criteria_service, scoring_service, threshold_service = build_env(
        [make_response('{"imports": []}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(required=True))
    threshold_service.set("criterion-imports-present", 0.5)

    run = run_service.run("case-notebook-analysis-1")

    failures = threshold_service.failures(run.run_id)
    assert len(failures) == 1
    assert failures[0]["criterion_id"] == "criterion-imports-present"
    assert threshold_service.passed(run.run_id) is False


def test_disabled_threshold():
    case_service, run_service, criteria_service, scoring_service, threshold_service = build_env(
        [make_response('{"imports": []}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(required=True))
    threshold_service.set("criterion-imports-present", 0.9)
    threshold_service.disable("criterion-imports-present")

    run = run_service.run("case-notebook-analysis-1")

    assert threshold_service.evaluate(run.run_id) == []
    assert threshold_service.failures(run.run_id) == []
    assert threshold_service.passed(run.run_id) is True


def test_overall_pass_fail():
    case_service, run_service, criteria_service, scoring_service, threshold_service = build_env(
        [make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}')]
    )
    case_service.register(
        make_case(expected_properties={"imports": ["pandas"], "dependencies": ["numpy"]})
    )
    criteria_service.register(
        make_criterion(criterion_id="criterion-required", required=True)
    )
    criteria_service.register(
        make_criterion(criterion_id="criterion-optional", name="optional check", required=False)
    )
    threshold_service.set("criterion-required", 0.9)
    threshold_service.set("criterion-optional", 0.9)

    passing_run = run_service.run("case-notebook-analysis-1")
    assert threshold_service.passed(passing_run.run_id) is True

    # Now the required criterion is disabled (excluded from scoring), so its
    # threshold sees a missing score; the optional criterion still passes,
    # but that alone cannot make the overall result pass.
    criteria_service.disable("criterion-required")

    failing_run = run_service.run("case-notebook-analysis-1")
    assert threshold_service.passed(failing_run.run_id) is False
