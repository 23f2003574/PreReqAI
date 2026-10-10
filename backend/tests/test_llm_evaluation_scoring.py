from datetime import datetime, timezone

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_criteria import LLMEvaluationCriteriaService, LLMEvaluationCriterion
from backend.llm.evaluation_criteria import UnknownEvaluationCriterionError
from backend.llm.evaluation_runs import LLMEvaluationRunService
from backend.llm.evaluation_scoring import (
    InvalidEvaluationScoreError,
    LLMEvaluationScore,
    LLMEvaluationScoringService,
    NoCriteriaRegisteredError,
    RunNotSucceededError,
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

    return case_service, run_service, criteria_service, scoring_service


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


def test_criterion_scoring():
    case_service, run_service, criteria_service, scoring_service = build_env(
        [make_response('{"imports": ["pandas", "os"]}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())
    run = run_service.run("case-notebook-analysis-1")

    score = scoring_service.score_criterion(run.run_id, "criterion-imports-present")

    assert score.run_id == run.run_id
    assert score.criterion_id == "criterion-imports-present"
    assert score.score == 1.0
    assert "imports are present" in score.rationale
    assert "imports" in score.rationale


def test_weighted_overall_score():
    case_service, run_service, criteria_service, scoring_service = build_env(
        [make_response('{"imports": ["pandas"]}')]
    )
    case_service.register(
        make_case(expected_properties={"imports": ["pandas"], "dependencies": ["numpy"]})
    )
    criteria_service.register(make_criterion(criterion_id="criterion-a", name="criterion a", weight=3.0))
    criteria_service.register(make_criterion(criterion_id="criterion-b", name="criterion b", weight=1.0))
    run = run_service.run("case-notebook-analysis-1")

    scores = scoring_service.score(run.run_id)
    assert len(scores) == 2
    # imports matches, dependencies does not -> ratio 0.5 for every criterion
    assert all(s.score == 0.5 for s in scores)

    overall = scoring_service.overall(run.run_id)
    assert overall == 0.5


def test_missing_criterion():
    case_service, run_service, criteria_service, scoring_service = build_env(
        [make_response('{"imports": ["pandas"]}')]
    )
    case_service.register(make_case())
    run = run_service.run("case-notebook-analysis-1")

    with pytest.raises(UnknownEvaluationCriterionError):
        scoring_service.score_criterion(run.run_id, "does-not-exist")


def test_invalid_score():
    valid = LLMEvaluationScore(
        score_id="s1",
        run_id="r1",
        criterion_id="c1",
        score=0.5,
        rationale="matched",
        evaluated_at=datetime.now(timezone.utc),
    )
    valid.validate()

    with pytest.raises(InvalidEvaluationScoreError):
        LLMEvaluationScore(
            score_id="s1",
            run_id="r1",
            criterion_id="c1",
            score=1.5,
            rationale="matched",
            evaluated_at=datetime.now(timezone.utc),
        ).validate()

    with pytest.raises(InvalidEvaluationScoreError):
        LLMEvaluationScore(
            score_id="s1",
            run_id="r1",
            criterion_id="c1",
            score=-0.1,
            rationale="matched",
            evaluated_at=datetime.now(timezone.utc),
        ).validate()

    with pytest.raises(InvalidEvaluationScoreError):
        LLMEvaluationScore(
            score_id="s1",
            run_id="r1",
            criterion_id="c1",
            score=0.5,
            rationale="",
            evaluated_at=datetime.now(timezone.utc),
        ).validate()


def test_failed_run():
    case_service, run_service, criteria_service, scoring_service = build_env(
        [RuntimeError("provider exploded")]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())
    run = run_service.run("case-notebook-analysis-1")

    with pytest.raises(RunNotSucceededError):
        scoring_service.score(run.run_id)

    with pytest.raises(RunNotSucceededError):
        scoring_service.score_criterion(run.run_id, "criterion-imports-present")


def test_no_criteria_registered():
    case_service, run_service, criteria_service, scoring_service = build_env(
        [make_response('{"imports": ["pandas"]}')]
    )
    case_service.register(make_case())
    run = run_service.run("case-notebook-analysis-1")

    with pytest.raises(NoCriteriaRegisteredError):
        scoring_service.score(run.run_id)


def test_required_criterion():
    case_service, run_service, criteria_service, scoring_service = build_env(
        [make_response('{"imports": ["pandas"]}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion(criterion_id="criterion-required", required=True))
    criteria_service.register(
        make_criterion(criterion_id="criterion-optional", name="optional check", required=False)
    )
    run = run_service.run("case-notebook-analysis-1")

    scores = scoring_service.score(run.run_id)
    scored_ids = {s.criterion_id for s in scores}

    assert "criterion-required" in scored_ids
    assert "criterion-optional" in scored_ids


def test_deterministic_aggregation():
    case_service, run_service, criteria_service, scoring_service = build_env(
        [make_response('{"imports": ["pandas"]}')]
    )
    case_service.register(make_case())
    criteria_service.register(make_criterion())
    run = run_service.run("case-notebook-analysis-1")

    first = scoring_service.overall(run.run_id)
    second = scoring_service.overall(run.run_id)

    assert first == second == 1.0
