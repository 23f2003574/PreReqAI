import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_documentation import LLMAPIDocumentationService, MalformedDocumentationResponseError, UnsupportedClaimError
from backend.api_documentation_draft import (
    DRAFT,
    VALIDATED,
    LLMAPIDocumentationDraftService,
    SchemaNotApprovedError,
    UnknownDraftError,
)
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_schema_review import LLMAPISchemaReviewService
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_api_intent import LLMNotebookAPIIntent
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
    documentation_service = LLMAPIDocumentationService(
        api_candidate_service,
        notebook_analysis_service,
        input_schema_service,
        output_schema_service,
        orchestration_service,
        context_service,
    )
    exposure_service = LLMAPIExposureService(notebook_analysis_service, orchestration_service, context_service)
    schema_review_service = LLMAPISchemaReviewService(
        exposure_service,
        api_candidate_service,
        input_schema_service,
        output_schema_service,
        orchestration_service,
        context_service,
    )
    draft_service = LLMAPIDocumentationDraftService(
        exposure_service, schema_review_service, api_candidate_service, documentation_service
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "documentation": documentation_service,
        "exposure": exposure_service,
        "review": schema_review_service,
        "draft": draft_service,
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
REJECTED_REVIEW_RESPONSE = json.dumps(
    {
        "findings": [
            {"category": "AMBIGUOUS_TYPE", "target": "a", "message": "too vague.", "blocking": True}
        ],
        "confidence": 0.4,
    }
)
DOC_RESPONSE = json.dumps(
    {
        "summary": "Adds two numbers.",
        "description": "Adds the two given integers and returns their sum.",
        "examples": [{"input": {"a": 1, "b": 2}, "output": {"sum": 3}}],
    }
)
UNSUPPORTED_CLAIM_DOC_RESPONSE = json.dumps(
    {
        "summary": "Adds two numbers.",
        "description": "Adds the two given integers and returns their sum.",
        "examples": [{"input": {"a": 1, "b": 2, "c": 5}, "output": {"sum": 3}}],
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


def _approved_recommendation(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)
    return recommendation


def test_documentation_generation_reuses_the_existing_documentation_service():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(DOC_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)

    draft = env["draft"].generate(recommendation)

    assert draft.endpoint == "POST /add"
    assert draft.status == DRAFT
    assert draft.summary == "Adds two numbers."
    assert draft.examples == [{"input": {"a": 1, "b": 2}, "output": {"sum": 3}}]
    assert env["draft"].get(draft.draft_id) == draft


def test_parameters_and_responses_match_the_underlying_documentation_exactly():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(DOC_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)

    draft = env["draft"].generate(recommendation)

    underlying = env["documentation"].get(env["api_candidate"].candidates("nb-1")[0].candidate_id)
    assert draft.parameters == underlying.parameters
    assert draft.responses == underlying.response
    assert draft.examples == underlying.examples


def test_unsupported_claim_is_rejected_by_the_underlying_service():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(UNSUPPORTED_CLAIM_DOC_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)

    with pytest.raises(UnsupportedClaimError):
        env["draft"].generate(recommendation)


def test_malformed_documentation_response_propagates():
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
    recommendation = _approved_recommendation(env)

    with pytest.raises(MalformedDocumentationResponseError):
        env["draft"].generate(recommendation)


def test_validate_transitions_a_draft_from_draft_to_validated():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(DOC_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)
    draft = env["draft"].generate(recommendation)
    assert draft.status == DRAFT

    validated = env["draft"].validate(draft)

    assert validated.status == VALIDATED
    assert validated.draft_id == draft.draft_id
    assert env["draft"].get(draft.draft_id).status == VALIDATED

    with pytest.raises(UnknownDraftError):
        env["draft"].validate(
            draft.__class__(
                draft_id="never-generated",
                endpoint=draft.endpoint,
                summary=draft.summary,
                description=draft.description,
                parameters=draft.parameters,
                responses=draft.responses,
                examples=draft.examples,
                status=DRAFT,
            )
        )


def test_generation_requires_an_approved_schema_review():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
        ]
    )
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    # Deliberately never schema-reviewed.

    with pytest.raises(SchemaNotApprovedError):
        env["draft"].generate(recommendation)

    # A separately reviewed-and-rejected recommendation still blocks drafting.
    rejected_env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(REJECTED_REVIEW_RESPONSE),
        ]
    )
    rejected_analysis = rejected_env["notebook_analysis"].analyze(NOTEBOOK)
    [rejected_candidate] = rejected_env["api_candidate"].analyze(rejected_analysis.analysis_id)
    rejected_env["input_schema"].infer(rejected_candidate.candidate_id)
    rejected_env["output_schema"].infer(rejected_candidate.candidate_id)
    [rejected_recommendation] = rejected_env["exposure"].recommend(_confident_intent())
    rejected_env["review"].review(rejected_recommendation)

    with pytest.raises(SchemaNotApprovedError):
        rejected_env["draft"].generate(rejected_recommendation)
