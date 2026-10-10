import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService
from backend.llm.evaluation_dataset_runs import (
    COMPLETED,
    DisabledEvaluationDatasetError,
    LLMEvaluationDatasetRunService,
    UnknownEvaluationDatasetRunError,
)
from backend.llm.evaluation_datasets import LLMEvaluationDatasetService
from backend.llm.evaluation_runs import FAILED, SUCCEEDED, LLMEvaluationRunService
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
    dataset_service = LLMEvaluationDatasetService(case_service)
    dataset_run_service = LLMEvaluationDatasetRunService(dataset_service, run_service)

    return case_service, run_service, dataset_service, dataset_run_service


def make_case(case_id, **overrides):
    fields = {
        "case_id": case_id,
        "name": f"case {case_id}",
        "task_type": "notebook_analysis",
        "input": {"notebook_id": case_id, "cells": [{"index": 0, "cell_type": "code", "source": "import pandas"}]},
        "expected_properties": {"imports": ["pandas"]},
    }
    fields.update(overrides)
    return LLMEvaluationCase(**fields)


def test_full_dataset_run():
    case_service, run_service, dataset_service, dataset_run_service = build_env(
        [make_response("a"), make_response("b"), make_response("c")]
    )
    for case_id in ("case-a", "case-b", "case-c"):
        case_service.register(make_case(case_id))
    dataset = dataset_service.create(
        "notebook benchmark", "notebook_analysis", ["case-a", "case-b", "case-c"]
    )

    dataset_run = dataset_run_service.run(dataset.dataset_id, provider="openai", model="gpt-4o")

    assert len(dataset_run.case_runs) == 3
    assert dataset_run.status == COMPLETED
    assert dataset_run.provider == "openai"
    assert dataset_run.model == "gpt-4o"
    assert dataset_run.started_at <= dataset_run.completed_at


def test_disabled_dataset():
    case_service, run_service, dataset_service, dataset_run_service = build_env([make_response("a")])
    case_service.register(make_case("case-a"))
    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a"])
    dataset_service.disable(dataset.dataset_id)

    with pytest.raises(DisabledEvaluationDatasetError):
        dataset_run_service.run(dataset.dataset_id, provider="openai", model="gpt-4o")


def test_disabled_case_handling():
    case_service, run_service, dataset_service, dataset_run_service = build_env(
        [make_response("a"), make_response("c")]
    )
    for case_id in ("case-a", "case-b", "case-c"):
        case_service.register(make_case(case_id))
    dataset = dataset_service.create(
        "notebook benchmark", "notebook_analysis", ["case-a", "case-b", "case-c"]
    )
    case_service.disable("case-b")

    dataset_run = dataset_run_service.run(dataset.dataset_id, provider="openai", model="gpt-4o")

    case_ids_run = [
        run.case_id for run in dataset_run_service.case_runs(dataset_run.dataset_run_id)
    ]
    assert case_ids_run == ["case-a", "case-c"]


def test_case_failure_recorded():
    case_service, run_service, dataset_service, dataset_run_service = build_env(
        [make_response("a"), RuntimeError("provider exploded"), make_response("c")]
    )
    for case_id in ("case-a", "case-b", "case-c"):
        case_service.register(make_case(case_id))
    dataset = dataset_service.create(
        "notebook benchmark", "notebook_analysis", ["case-a", "case-b", "case-c"]
    )

    dataset_run = dataset_run_service.run(dataset.dataset_id, provider="openai", model="gpt-4o")

    assert len(dataset_run.case_runs) == 3
    runs = dataset_run_service.case_runs(dataset_run.dataset_run_id)
    statuses = {run.case_id: run.status for run in runs}
    assert statuses == {"case-a": SUCCEEDED, "case-b": FAILED, "case-c": SUCCEEDED}


def test_ordering():
    case_service, run_service, dataset_service, dataset_run_service = build_env(
        [make_response("b"), make_response("a"), make_response("c")]
    )
    for case_id in ("case-b", "case-a", "case-c"):
        case_service.register(make_case(case_id))
    dataset = dataset_service.create(
        "notebook benchmark", "notebook_analysis", ["case-b", "case-a", "case-c"]
    )

    dataset_run = dataset_run_service.run(dataset.dataset_id, provider="openai", model="gpt-4o")

    ordered_case_ids = [
        run.case_id for run in dataset_run_service.case_runs(dataset_run.dataset_run_id)
    ]
    assert ordered_case_ids == ["case-b", "case-a", "case-c"]


def test_provider_model_recording():
    case_service, run_service, dataset_service, dataset_run_service = build_env(
        [make_response("a"), make_response("b")]
    )
    for case_id in ("case-a", "case-b"):
        case_service.register(make_case(case_id))
    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a", "case-b"])

    dataset_run = dataset_run_service.run(dataset.dataset_id, provider="openai", model="gpt-4o")

    assert dataset_run.provider == "openai"
    assert dataset_run.model == "gpt-4o"
    for run in dataset_run_service.case_runs(dataset_run.dataset_run_id):
        assert run.provider == "openai"
        assert run.model == "gpt-4o"


def test_run_completion_state():
    case_service, run_service, dataset_service, dataset_run_service = build_env([make_response("a")])
    case_service.register(make_case("case-a"))
    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a"])

    dataset_run = dataset_run_service.run(dataset.dataset_id, provider="openai", model="gpt-4o")

    assert dataset_run_service.status(dataset_run.dataset_run_id) == COMPLETED
    assert len(dataset_run_service.case_runs(dataset_run.dataset_run_id)) == 1

    with pytest.raises(UnknownEvaluationDatasetRunError):
        dataset_run_service.status("does-not-exist")

    with pytest.raises(UnknownEvaluationDatasetRunError):
        dataset_run_service.case_runs("does-not-exist")
