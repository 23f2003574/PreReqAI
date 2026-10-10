import json
from datetime import datetime, timezone

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.code_transformation import OPTIMIZE, LLMCodeTransformationService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.transformation_approval import LLMTransformationApprovalService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import (
    SUCCEEDED,
    LLMTransformationExecution,
    LLMTransformationExecutionService,
    UnknownExecutionError,
)
from backend.transformation_optimization import (
    HIGH,
    LLMCodeOptimizationService,
    MalformedRecommendationResponseError,
    UnverifiedTransformationError,
)
from backend.transformation_validation import LLMTransformationValidationService
from backend.transformation_verification import LLMTransformationVerificationService


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays one scripted outcome per call, in order."""

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

    notebook_analysis_service = LLMNotebookAnalysisService(orchestration_service, context_service)
    transformation_service = LLMCodeTransformationService(
        notebook_analysis_service, orchestration_service, context_service
    )
    validation_service = LLMTransformationValidationService(
        transformation_service, notebook_analysis_service, orchestration_service, context_service
    )
    diff_service = LLMTransformationDiffService(
        transformation_service, validation_service, notebook_analysis_service
    )
    approval_service = LLMTransformationApprovalService(diff_service, validation_service)
    execution_service = LLMTransformationExecutionService(
        approval_service, diff_service, transformation_service, notebook_analysis_service
    )
    api_candidate_service = LLMAPICandidateService(
        notebook_analysis_service, orchestration_service=orchestration_service, context_service=context_service
    )
    verification_service = LLMTransformationVerificationService(
        execution_service, diff_service, transformation_service, api_candidate_service, None
    )
    optimization_service = LLMCodeOptimizationService(
        verification_service, execution_service, orchestration_service, context_service
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "transformation": transformation_service,
        "validation": validation_service,
        "diff": diff_service,
        "approval": approval_service,
        "execution": execution_service,
        "verification": verification_service,
        "optimization": optimization_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return {'sum': a + b}"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "add", "cell_index": 1}], "dependencies": []}
)
TRANSFORMATION_RESPONSE = json.dumps(
    {
        "changes": [
            {
                "cell_index": 1,
                "description": "Add type hints.",
                "proposed_source": "def add(a: int, b: int) -> dict:\n    return {'sum': a + b}",
            }
        ],
        "rationale": "Type hints improve readability.",
        "confidence": 0.9,
    }
)
EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})

REQUEST = {"target_cells": [1], "transformation_type": OPTIMIZE, "instructions": "optimize add"}

TWO_RECOMMENDATIONS_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "target": "1",
                "optimization": "Avoid rebuilding the result dict key on every call.",
                "expected_impact": {
                    "magnitude": "LOW",
                    "description": "Marginal reduction in per-call dict allocation overhead.",
                },
                "confidence": 0.6,
                "risk": "LOW",
            },
            {
                "target": "1",
                "optimization": "Hoist the computation out of any enclosing hot loop at call sites.",
                "expected_impact": {
                    "magnitude": "HIGH",
                    "description": "Profiling similar call patterns showed a 3x reduction in wall-clock time under high call volume.",
                },
                "confidence": 0.75,
                "risk": "MEDIUM",
            },
        ]
    }
)


def _happy_execution(env):
    plan = env["transformation"].plan("nb-1", REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    execution = env["execution"].apply(diff.diff_id)
    env["verification"].verify(execution.execution_id)
    return execution


def _verified_env_and_execution(optimization_response):
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(TRANSFORMATION_RESPONSE),
            make_response(EMPTY_FINDINGS_RESPONSE),
            make_response(optimization_response),
        ]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    execution = _happy_execution(env)
    return env, execution


def test_analyze_generates_grounded_recommendations():
    env, execution = _verified_env_and_execution(TWO_RECOMMENDATIONS_RESPONSE)

    recommendations = env["optimization"].analyze(execution.execution_id)

    assert len(recommendations) == 2
    for rec in recommendations:
        assert rec.execution_id == execution.execution_id
        assert rec.target == "1"
        assert rec.optimization.strip()
        assert rec.expected_impact["description"].strip()
    assert env["optimization"].recommendations(execution.execution_id) == recommendations


@pytest.mark.parametrize(
    "bad_response",
    [
        json.dumps(
            {
                "recommendations": [
                    {
                        "target": "1",
                        "optimization": "Something.",
                        "expected_impact": {"magnitude": "LOW", "description": "Some evidence."},
                        "confidence": 1.5,
                        "risk": "LOW",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "recommendations": [
                    {
                        "target": "1",
                        "optimization": "Something.",
                        "expected_impact": {"magnitude": "LOW", "description": "Some evidence."},
                        "confidence": 0.5,
                        "risk": "EXTREME",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "recommendations": [
                    {
                        "target": "1",
                        "optimization": "Something.",
                        "expected_impact": {"magnitude": "UNKNOWN", "description": "Some evidence."},
                        "confidence": 0.5,
                        "risk": "LOW",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "recommendations": [
                    {
                        "target": "1",
                        "optimization": "Something.",
                        "expected_impact": {"magnitude": "LOW", "description": "   "},
                        "confidence": 0.5,
                        "risk": "LOW",
                    }
                ]
            }
        ),
    ],
)
def test_confidence_and_risk_and_evidence_are_validated(bad_response):
    env, execution = _verified_env_and_execution(bad_response)

    with pytest.raises(MalformedRecommendationResponseError):
        env["optimization"].analyze(execution.execution_id)


def test_high_impact_filters_to_only_high_magnitude_recommendations():
    env, execution = _verified_env_and_execution(TWO_RECOMMENDATIONS_RESPONSE)
    env["optimization"].analyze(execution.execution_id)

    high_impact = env["optimization"].high_impact(execution.execution_id)

    assert len(high_impact) == 1
    assert high_impact[0].expected_impact["magnitude"] == HIGH
    assert high_impact[0].risk == "MEDIUM"


def test_unverified_execution_is_rejected():
    env = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(TRANSFORMATION_RESPONSE), make_response(EMPTY_FINDINGS_RESPONSE)]
    )
    env["notebook_analysis"].analyze(NOTEBOOK)
    plan = env["transformation"].plan("nb-1", REQUEST)
    env["validation"].validate(plan.plan_id)
    diff = env["diff"].generate(plan.plan_id)
    env["approval"].approve(diff.diff_id, "alice")
    execution = env["execution"].apply(diff.diff_id)
    # Deliberately never verified.

    with pytest.raises(UnverifiedTransformationError):
        env["optimization"].analyze(execution.execution_id)

    now = datetime.now(timezone.utc)
    broken_execution = LLMTransformationExecution(
        execution_id="execution-broken-1",
        diff_id="diff-broken-1",
        status=SUCCEEDED,
        applied_cells=(
            {
                "cell_index": 1,
                "original_source": "def add(a, b):\n    return {'sum': a + b}",
                "applied_source": "def add(a, b)\n    return {'sum': a + b}",
            },
        ),
        created_at=now,
        completed_at=now,
    )

    class FakeExecutionService:
        def get(self, execution_id):
            if execution_id != broken_execution.execution_id:
                raise UnknownExecutionError(execution_id)
            return broken_execution

    fake_execution_service = FakeExecutionService()
    verification_service = LLMTransformationVerificationService(
        fake_execution_service, None, None, None, None
    )
    verification_service.verify(broken_execution.execution_id)
    optimization_service = LLMCodeOptimizationService(verification_service, fake_execution_service, None, None)

    with pytest.raises(UnverifiedTransformationError):
        optimization_service.analyze(broken_execution.execution_id)


def test_analyzing_never_mutates_notebook_source():
    env, execution = _verified_env_and_execution(TWO_RECOMMENDATIONS_RESPONSE)

    live_before = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source
    env["optimization"].analyze(execution.execution_id)
    live_after = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source

    assert live_before == live_after == "def add(a: int, b: int) -> dict:\n    return {'sum': a + b}"
