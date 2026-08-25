import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_schema_review import LLMAPISchemaReviewService
from backend.api_security_review import (
    AUTH,
    CRITICAL,
    DATA,
    LLMAPISecurityService,
    MalformedSecurityResponseError,
    SECRETS,
)
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_api_intent import LLMNotebookAPIIntent
from backend.notebook_dependencies import LLMNotebookDependencyService
from backend.output_schema import LLMOutputSchemaService


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
    api_candidate_service = LLMAPICandidateService(
        notebook_analysis_service, orchestration_service=orchestration_service, context_service=context_service
    )
    input_schema_service = LLMInputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    output_schema_service = LLMOutputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    dependency_service = LLMNotebookDependencyService(notebook_analysis_service, orchestration_service, context_service)
    exposure_service = LLMAPIExposureService(notebook_analysis_service, orchestration_service, context_service)
    schema_review_service = LLMAPISchemaReviewService(
        exposure_service,
        api_candidate_service,
        input_schema_service,
        output_schema_service,
        orchestration_service,
        context_service,
    )
    security_service = LLMAPISecurityService(
        exposure_service,
        schema_review_service,
        api_candidate_service,
        notebook_analysis_service,
        dependency_service,
        orchestration_service,
        context_service,
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "dependency": dependency_service,
        "exposure": exposure_service,
        "review": schema_review_service,
        "security": security_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def load_dataset():\n    return [1, 2, 3]"},
        {"cell_type": "code", "source": "def add(a, b):\n    return {'sum': a + b + len(load_dataset())}"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "load_dataset", "cell_index": 1}, {"name": "add", "cell_index": 2}],
        "dependencies": [],
    }
)
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "add",
                "inputs": ["a", "b"],
                "outputs": ["sum"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            }
        ]
    }
)
INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            {"name": "a", "type": "int", "constraints": {}, "ambiguous": False},
            {"name": "b", "type": "int", "constraints": {}, "ambiguous": False},
        ]
    }
)
OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "sum", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "add",
                "endpoint_name": "/add",
                "method": "POST",
                "rationale": "Pure arithmetic function.",
                "confidence": 0.85,
            }
        ]
    }
)
EMPTY_REVIEW_RESPONSE = json.dumps({"findings": [], "confidence": 0.9})
DEPENDENCY_RESPONSE = json.dumps(
    {
        "edges": [
            {
                "source": "data:dataset",
                "target": "function:add",
                "dependency_type": "DATA",
                "confidence": 0.8,
            }
        ]
    }
)
EMPTY_SECURITY_RESPONSE = json.dumps({"findings": []})
LLM_SECURITY_FINDING_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "category": "INPUT",
                "severity": "WARNING",
                "evidence": "no upper bound constraint on 'a' could allow integer overflow abuse.",
                "confidence": 0.5,
            }
        ]
    }
)


def _confident_intent():
    return LLMNotebookAPIIntent(
        notebook_id="nb-1",
        operations=[{"operation": "expose add", "function": "add", "ambiguous": False}],
        candidate_functions=["add"],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.8,
    )


def _register_candidate(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    return analysis, candidate


def test_security_findings_are_grounded_across_categories():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(DEPENDENCY_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(LLM_SECURITY_FINDING_RESPONSE),
        ]
    )
    analysis, _candidate = _register_candidate(env)
    env["dependency"].analyze(analysis.analysis_id)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    # Deliberately never schema-reviewed.

    findings = env["security"].analyze(recommendation)

    categories = {f.category for f in findings}
    assert AUTH in categories
    assert DATA in categories
    assert "INPUT" in categories
    assert all(f.evidence.strip() for f in findings)
    auth_finding = next(f for f in findings if f.category == AUTH)
    assert auth_finding.severity == "ERROR"  # POST is mutating
    assert env["security"].findings("POST /add") == findings


@pytest.mark.parametrize(
    "bad_response",
    [
        json.dumps({"findings": [{"category": "UNKNOWN", "severity": "WARNING", "evidence": "x", "confidence": 0.5}]}),
        json.dumps({"findings": [{"category": "INPUT", "severity": "CATASTROPHIC", "evidence": "x", "confidence": 0.5}]}),
        json.dumps({"findings": [{"category": "INPUT", "severity": "WARNING", "evidence": "x", "confidence": 1.5}]}),
    ],
)
def test_category_and_severity_are_validated(bad_response):
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(bad_response),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    with pytest.raises(MalformedSecurityResponseError):
        env["security"].analyze(recommendation)


def test_finding_without_evidence_is_rejected():
    empty_evidence_response = json.dumps(
        {"findings": [{"category": "INPUT", "severity": "WARNING", "evidence": "   ", "confidence": 0.5}]}
    )
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(empty_evidence_response),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    with pytest.raises(MalformedSecurityResponseError):
        env["security"].analyze(recommendation)


SECRET_NOTEBOOK = {
    "notebook_id": "nb-2",
    "cells": [
        {
            "cell_type": "code",
            "source": "def call_api(a, b):\n    api_key = 'sk-abcdEFGH12345678ijkl'\n    return {'sum': a + b}",
        }
    ],
}
SECRET_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "call_api", "cell_index": 0}], "dependencies": []}
)
SECRET_CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "call_api",
                "inputs": ["a", "b"],
                "outputs": ["sum"],
                "confidence": 0.9,
                "rationale": "Calls an external API.",
            }
        ]
    }
)
SECRET_INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            {"name": "a", "type": "int", "constraints": {}, "ambiguous": False},
            {"name": "b", "type": "int", "constraints": {}, "ambiguous": False},
        ]
    }
)
SECRET_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "sum", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
SECRET_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "call_api",
                "endpoint_name": "/call",
                "method": "POST",
                "rationale": "Calls an external API.",
                "confidence": 0.5,
            }
        ]
    }
)


def test_critical_filtering_flags_hardcoded_secrets():
    env = build_env(
        [
            make_response(SECRET_ANALYSIS_RESPONSE),
            make_response(SECRET_CANDIDATE_RESPONSE),
            make_response(SECRET_INPUT_SCHEMA_RESPONSE),
            make_response(SECRET_OUTPUT_SCHEMA_RESPONSE),
            make_response(SECRET_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_SECURITY_RESPONSE),
        ]
    )
    analysis = env["notebook_analysis"].analyze(SECRET_NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    intent = LLMNotebookAPIIntent(
        notebook_id="nb-2",
        operations=[{"operation": "expose call_api", "function": "call_api", "ambiguous": False}],
        candidate_functions=["call_api"],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.5,
    )
    [recommendation] = env["exposure"].recommend(intent)
    env["review"].review(recommendation)

    env["security"].analyze(recommendation)

    assert env["security"].blocking("POST /call") is True
    secret_findings = [f for f in env["security"].findings("POST /call") if f.category == SECRETS]
    assert any(f.severity == CRITICAL for f in secret_findings)


def test_malformed_llm_response_is_rejected():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response("not json"),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    with pytest.raises(MalformedSecurityResponseError):
        env["security"].analyze(recommendation)


SUB_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "load_dataset",
                "endpoint_name": "/dataset",
                "method": "GET",
                "rationale": "Exposes the dataset loader directly.",
                "confidence": 0.5,
            }
        ]
    }
)


def test_endpoint_isolation_keeps_findings_scoped():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_SECURITY_RESPONSE),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    env["security"].analyze(recommendation)

    assert env["security"].findings("POST /add")
    assert env["security"].findings("GET /dataset") == []
    assert env["security"].blocking("GET /dataset") is False
