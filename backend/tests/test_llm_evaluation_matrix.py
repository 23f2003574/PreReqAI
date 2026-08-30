import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_comparison import IncompatibleEvaluationCasesError
from backend.llm.evaluation_criteria import LLMEvaluationCriteriaService, LLMEvaluationCriterion
from backend.llm.evaluation_matrix import LLMEvaluationMatrixService
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
        return ["scripted-model"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(content, model):
    return LLMResponse(content=content, model=model, usage={"total_tokens": 15})


def build_env(openai_script, gemini_script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=False)
    )
    config_service.register(
        LLMProviderConfig(
            provider="gemini", model="gemini-1.5-pro", api_key_ref="GEMINI_KEY", enabled=False
        )
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )
    routing_service.register_capability_profile(
        "gemini", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={
            "openai": ScriptedProvider(openai_script),
            "gemini": ScriptedProvider(gemini_script),
        },
    )

    case_service = LLMEvaluationCaseService()
    run_service = LLMEvaluationRunService(orchestration_service, context_service, case_service)
    criteria_service = LLMEvaluationCriteriaService()
    scoring_service = LLMEvaluationScoringService(run_service, case_service, criteria_service)
    matrix_service = LLMEvaluationMatrixService(
        run_service, case_service, criteria_service, scoring_service
    )

    return config_service, case_service, run_service, criteria_service, scoring_service, matrix_service


def run_via(config_service, run_service, provider, case_id):
    """Run case_id, forcing the given provider by disabling the other one first."""
    for name in ("openai", "gemini"):
        if name == provider:
            config_service.enable(name)
        else:
            config_service.disable(name)
    return run_service.run(case_id)


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


def test_matrix_construction():
    config_service, case_service, run_service, criteria_service, scoring_service, matrix_service = (
        build_env(
            [make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}', "gpt-4o")],
            [make_response("ignored", "gemini-1.5-pro")],
        )
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    run = run_via(config_service, run_service, "openai", "case-notebook-analysis-1")
    matrix = matrix_service.build("notebook_analysis", [run.run_id])

    assert matrix.task_type == "notebook_analysis"
    assert matrix.runs == [run.run_id]
    assert matrix.criteria == ["criterion-imports-present"]
    assert set(matrix.aggregate_scores) == {"by_provider", "by_model"}
    assert matrix.aggregate_scores["by_provider"]["openai"]["overall"] == 1.0
    assert matrix.aggregate_scores["by_provider"]["openai"]["run_count"] == 1


def test_provider_and_model_aggregation():
    config_service, case_service, run_service, criteria_service, scoring_service, matrix_service = (
        build_env(
            [make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}', "gpt-4o")],
            [make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}', "gemini-1.5-pro")],
        )
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    openai_run = run_via(config_service, run_service, "openai", "case-notebook-analysis-1")
    gemini_run = run_via(config_service, run_service, "gemini", "case-notebook-analysis-1")

    matrix = matrix_service.build("notebook_analysis", [openai_run.run_id, gemini_run.run_id])

    provider_scores = matrix_service.provider_scores(matrix.matrix_id)
    assert provider_scores["openai"]["overall"] == 1.0
    assert provider_scores["openai"]["run_count"] == 1
    assert provider_scores["gemini"]["overall"] == 1.0
    assert provider_scores["gemini"]["run_count"] == 1

    model_scores = matrix_service.model_scores(matrix.matrix_id)
    assert set(model_scores) == {("openai", "gpt-4o"), ("gemini", "gemini-1.5-pro")}
    assert model_scores[("openai", "gpt-4o")]["run_ids"] == [openai_run.run_id]
    assert model_scores[("gemini", "gemini-1.5-pro")]["run_ids"] == [gemini_run.run_id]


def test_missing_run_never_treated_as_zero():
    config_service, case_service, run_service, criteria_service, scoring_service, matrix_service = (
        build_env(
            [RuntimeError("provider exploded")],
            [make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}', "gemini-1.5-pro")],
        )
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    failed_run = run_via(config_service, run_service, "openai", "case-notebook-analysis-1")
    ok_run = run_via(config_service, run_service, "gemini", "case-notebook-analysis-1")

    matrix = matrix_service.build("notebook_analysis", [failed_run.run_id, ok_run.run_id])

    provider_scores = matrix_service.provider_scores(matrix.matrix_id)
    assert provider_scores["openai"]["overall"] is None
    assert provider_scores["openai"]["run_count"] == 0
    assert provider_scores["openai"]["excluded_run_ids"] == [failed_run.run_id]
    assert provider_scores["gemini"]["overall"] == 1.0


def test_incompatible_case():
    config_service, case_service, run_service, criteria_service, scoring_service, matrix_service = (
        build_env(
            [make_response('{"imports": ["pandas"]}', "gpt-4o")],
            [make_response("ignored", "gemini-1.5-pro")],
        )
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

    run = run_via(config_service, run_service, "openai", "case-api-candidate-1")

    with pytest.raises(IncompatibleEvaluationCasesError):
        matrix_service.build("notebook_analysis", [run.run_id])


def test_ranking():
    config_service, case_service, run_service, criteria_service, scoring_service, matrix_service = (
        build_env(
            [make_response('{"imports": []}', "gpt-4o")],
            [make_response('{"imports": ["pandas"], "dependencies": ["numpy"]}', "gemini-1.5-pro")],
        )
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    weak_run = run_via(config_service, run_service, "openai", "case-notebook-analysis-1")
    strong_run = run_via(config_service, run_service, "gemini", "case-notebook-analysis-1")

    matrix = matrix_service.build("notebook_analysis", [weak_run.run_id, strong_run.run_id])

    best = matrix_service.best(matrix.matrix_id)
    assert best["provider"] == "gemini"
    assert best["model"] == "gemini-1.5-pro"
    assert best["overall"] == 1.0


def test_deterministic_best_model_selection():
    same_output = '{"imports": ["pandas"], "dependencies": ["numpy"]}'
    config_service, case_service, run_service, criteria_service, scoring_service, matrix_service = (
        build_env(
            [make_response(same_output, "gpt-4o")],
            [make_response(same_output, "gemini-1.5-pro")],
        )
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())

    openai_run = run_via(config_service, run_service, "openai", "case-notebook-analysis-1")
    gemini_run = run_via(config_service, run_service, "gemini", "case-notebook-analysis-1")

    matrix = matrix_service.build("notebook_analysis", [openai_run.run_id, gemini_run.run_id])

    first = matrix_service.best(matrix.matrix_id)
    second = matrix_service.best(matrix.matrix_id)

    # Tied overall scores: tie-break is alphabetical by provider ("gemini" < "openai").
    assert first == second
    assert first["provider"] == "gemini"
