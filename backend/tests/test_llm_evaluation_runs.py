import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService, UnknownEvaluationCaseError
from backend.llm.evaluation_runs import (
    FAILED,
    SUCCEEDED,
    DisabledEvaluationCaseError,
    LLMEvaluationRunService,
    UnknownEvaluationRunError,
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

    return case_service, run_service


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


def test_successful_run():
    case_service, run_service = build_env([make_response("the model's raw answer")])
    case_service.register(make_case())

    run = run_service.run("case-notebook-analysis-1")

    assert run.status == SUCCEEDED
    assert run.case_id == "case-notebook-analysis-1"
    assert run.output == "the model's raw answer"
    assert run.started_at <= run.completed_at
    assert run_service.get(run.run_id) is run


def test_disabled_case():
    case_service, run_service = build_env([make_response("ok")])
    case_service.register(make_case(enabled=False))

    with pytest.raises(DisabledEvaluationCaseError):
        run_service.run("case-notebook-analysis-1")


def test_unknown_case():
    _, run_service = build_env([make_response("ok")])

    with pytest.raises(UnknownEvaluationCaseError):
        run_service.run("does-not-exist")


def test_provider_failure():
    case_service, run_service = build_env([RuntimeError("provider exploded")])
    case_service.register(make_case())

    run = run_service.run("case-notebook-analysis-1")

    assert run.status == FAILED
    assert run.output is None
    assert run.provider == "openai"
    assert run.model == "gpt-4o"
    assert run_service.get(run.run_id).status == FAILED


def test_result_capture():
    case_service, run_service = build_env([make_response('{"imports": ["pandas"]}')])
    case_service.register(make_case())

    run = run_service.run("case-notebook-analysis-1")

    assert run.output == '{"imports": ["pandas"]}'


def test_provider_model_recording():
    case_service, run_service = build_env([make_response("ok")])
    case_service.register(make_case())

    run = run_service.run("case-notebook-analysis-1")

    assert run.provider == "openai"
    assert run.model == "gpt-4o"


def test_secret_exclusion():
    case_service, run_service = build_env(
        [make_response("here is a key: sk-liveAbCdEfGhIjKlMnOpQrSt for you")]
    )
    case_service.register(make_case())

    run = run_service.run("case-notebook-analysis-1")

    assert run.status == SUCCEEDED
    assert run.output == "[REDACTED]"
    assert "sk-live" not in (run.output or "")


def test_history_and_unknown_run():
    case_service, run_service = build_env([make_response("first"), make_response("second")])
    case_service.register(make_case())

    first_run = run_service.run("case-notebook-analysis-1")
    second_run = run_service.run("case-notebook-analysis-1")

    assert run_service.history("case-notebook-analysis-1") == [first_run, second_run]
    assert run_service.history("no-runs-here") == []

    with pytest.raises(UnknownEvaluationRunError):
        run_service.get("does-not-exist")
