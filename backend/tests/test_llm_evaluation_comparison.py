import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_comparison import (
    BASELINE,
    CANDIDATE,
    TIE,
    IncompatibleEvaluationCasesError,
    LLMEvaluationComparisonService,
)
from backend.llm.evaluation_criteria import LLMEvaluationCriteriaService, LLMEvaluationCriterion
from backend.llm.evaluation_runs import LLMEvaluationRunService
from backend.llm.evaluation_scoring import LLMEvaluationScoringService
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
    comparison_service = LLMEvaluationComparisonService(run_service, case_service, scoring_service)

    return case_service, run_service, criteria_service, scoring_service, comparison_service


def make_case(**overrides):
    fields = {
        "case_id": "case-notebook-analysis-1",
        "name": "notebook analysis extracts imports",
        "task_type": "notebook_analysis",
        "input": {"notebook_id": "nb-1", "cells": [{"index": 0, "cell_type": "code", "source": "import pandas"}]},
        "expected_properties": {"imports": ["pandas"], "dependencies": ["numpy"]},
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


def test_matching_runs():
    case_service, run_service, criteria_service, scoring_service, comparison_service = build_env(
        [
            make_response('{"imports": []}'),
            make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}'),
        ]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    comparison = comparison_service.compare(baseline.run_id, candidate.run_id)

    assert comparison.baseline_run == baseline.run_id
    assert comparison.candidate_run == candidate.run_id
    assert set(comparison.criterion_deltas) == {"criterion-imports-present"}
    assert comparison.winner == CANDIDATE
    assert comparison.overall_delta > 0


def test_criterion_deltas():
    case_service, run_service, criteria_service, scoring_service, comparison_service = build_env(
        [
            make_response('{"imports": []}'),
            make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}'),
        ]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(criterion_id="criterion-a", name="criterion a", weight=1.0))
    criteria_service.register(make_criterion(criterion_id="criterion-b", name="criterion b", weight=2.0))

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    entry_a = comparison_service.criterion_delta(baseline.run_id, candidate.run_id, "criterion-a")
    assert entry_a["baseline_score"] == 0.0
    assert entry_a["candidate_score"] == 1.0
    assert entry_a["delta"] == 1.0

    comparison = comparison_service.compare(baseline.run_id, candidate.run_id)
    assert comparison.criterion_deltas["criterion-a"] == entry_a
    assert comparison.criterion_deltas["criterion-b"]["delta"] == 1.0


def test_overall_delta():
    case_service, run_service, criteria_service, scoring_service, comparison_service = build_env(
        [
            make_response('{"imports": []}'),
            make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}'),
        ]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    expected = round(
        scoring_service.overall(candidate.run_id) - scoring_service.overall(baseline.run_id), 6
    )
    assert comparison_service.overall_delta(baseline.run_id, candidate.run_id) == expected


def test_missing_criterion():
    case_service, run_service, criteria_service, scoring_service, comparison_service = build_env(
        [make_response('{"imports": ["pandas"]}'), make_response('{"imports": ["pandas"]}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(criterion_id="criterion-active"))
    criteria_service.register(make_criterion(criterion_id="criterion-disabled", name="disabled check"))
    criteria_service.disable("criterion-disabled")

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    entry = comparison_service.criterion_delta(baseline.run_id, candidate.run_id, "criterion-disabled")
    assert entry == {
        "criterion_id": "criterion-disabled",
        "baseline_score": None,
        "candidate_score": None,
        "delta": None,
    }

    comparison = comparison_service.compare(baseline.run_id, candidate.run_id)
    assert "criterion-disabled" not in comparison.criterion_deltas
    assert "criterion-active" in comparison.criterion_deltas


def test_incompatible_cases():
    case_service, run_service, criteria_service, scoring_service, comparison_service = build_env(
        [make_response('{"imports": ["pandas"]}'), make_response('{"is_candidate": true}')]
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
        comparison_service.compare(notebook_run.run_id, api_run.run_id)

    with pytest.raises(IncompatibleEvaluationCasesError):
        comparison_service.overall_delta(notebook_run.run_id, api_run.run_id)

    with pytest.raises(IncompatibleEvaluationCasesError):
        comparison_service.criterion_delta(notebook_run.run_id, api_run.run_id, "criterion-imports-present")


def test_identical_scores():
    same_output = '{"imports": ["pandas"], "dependencies": ["numpy"]}'
    case_service, run_service, criteria_service, scoring_service, comparison_service = build_env(
        [make_response(same_output), make_response(same_output)]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    comparison = comparison_service.compare(baseline.run_id, candidate.run_id)

    assert comparison.overall_delta == 0.0
    assert comparison.winner == TIE
    assert all(entry["delta"] == 0.0 for entry in comparison.criterion_deltas.values())


def test_deterministic_winner():
    case_service, run_service, criteria_service, scoring_service, comparison_service = build_env(
        [
            make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}'),
            make_response('{"imports": []}'),
        ]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    baseline = run_service.run("case-notebook-analysis-1")
    candidate = run_service.run("case-notebook-analysis-1")

    first = comparison_service.compare(baseline.run_id, candidate.run_id)
    second = comparison_service.compare(baseline.run_id, candidate.run_id)

    assert first.winner == second.winner == BASELINE
    assert first.overall_delta == second.overall_delta
