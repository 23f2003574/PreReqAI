import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.compilation_execution import (
    Compiler,
    CompilerError,
    CompilerJobResult,
    InvalidCompilerOutputError,
    LLMCompilationExecutionService,
    PlanNotApprovedError,
    UnknownExecutionError,
    UnreviewedPlanError,
)
from backend.compilation_plan import LLMCompilationPlanningService
from backend.compilation_review import LLMCompilationReviewService
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
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


class ScriptedCompiler(Compiler):
    """A real Compiler that replays one scripted outcome per call, in order."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def compile(self, compiler_input):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


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
    candidate_service = LLMAPICandidateService(
        notebook_analysis_service,
        orchestration_service=orchestration_service,
        context_service=context_service,
    )
    input_schema_service = LLMInputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    output_schema_service = LLMOutputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    dependency_service = LLMNotebookDependencyService(
        notebook_analysis_service, orchestration_service, context_service
    )
    plan_service = LLMCompilationPlanningService(
        candidate_service,
        notebook_analysis_service,
        input_schema_service,
        output_schema_service,
        dependency_service,
        orchestration_service,
        context_service,
    )
    review_service = LLMCompilationReviewService(plan_service, orchestration_service, context_service)

    return {
        "notebook_analysis": notebook_analysis_service,
        "candidate": candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "dependency": dependency_service,
        "plan": plan_service,
        "review": review_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [{"cell_type": "code", "source": "def add(a: int, b: int) -> int:\n    return a + b"}],
}
FUNCTIONS = [{"name": "add", "cell_index": 0}]
ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": FUNCTIONS, "dependencies": []})
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "add",
                "inputs": ["a", "b"],
                "outputs": ["result"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            }
        ]
    }
)


def input_field_entry(name, field_type="float"):
    return {"name": name, "type": field_type, "constraints": {}, "ambiguous": False}


INPUT_SCHEMA_RESPONSE = json.dumps({"fields": [input_field_entry("a"), input_field_entry("b")]})


def output_field_entry(name, field_type="str"):
    return {"name": name, "type": field_type, "nullable": False, "structure": {}, "contradictory": False}


OUTPUT_SCHEMA_RESPONSE = json.dumps({"fields": [output_field_entry("result")]})
DEPENDENCY_RESPONSE = json.dumps(
    {
        "edges": [
            {"source": "cell:0", "target": "function:add", "dependency_type": "FUNCTION", "confidence": 0.9}
        ]
    }
)

CANDIDATE_ID = "candidate-nb-1-1"
ENDPOINTS_RESPONSE = json.dumps(
    {"endpoints": [{"candidate_id": CANDIDATE_ID, "method": "POST", "path": "/add"}]}
)
EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": []})
BLOCKING_FINDING_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "category": "UNSAFE_DECISION",
                "target": CANDIDATE_ID,
                "message": "No rate limiting guidance.",
                "blocking": True,
            }
        ]
    }
)


def build_reviewed_plan(review_response=EMPTY_FINDINGS_RESPONSE):
    services = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(DEPENDENCY_RESPONSE),
            make_response(ENDPOINTS_RESPONSE),
            make_response(review_response),
        ]
    )
    analysis = services["notebook_analysis"].analyze(NOTEBOOK)
    candidates = services["candidate"].analyze(analysis.analysis_id)
    assert candidates[0].candidate_id == CANDIDATE_ID

    services["input_schema"].infer(CANDIDATE_ID)
    services["output_schema"].infer(CANDIDATE_ID)
    services["dependency"].analyze(analysis.analysis_id)

    plan = services["plan"].build("nb-1")
    services["review"].review(plan.plan_id)

    return services, plan


def test_approved_plan_execution():
    services, plan = build_reviewed_plan()
    compiler = ScriptedCompiler([CompilerJobResult(job_id="job-1", status="SUCCEEDED", output={"ok": True})])
    execution_service = LLMCompilationExecutionService(services["plan"], services["review"], compiler)

    execution = execution_service.execute(plan.plan_id)

    assert execution.plan_id == plan.plan_id
    assert execution.compiler_job_id == "job-1"
    assert execution.status == "SUCCEEDED"
    assert execution.created_at is not None
    assert execution.completed_at is not None
    assert compiler.calls == 1


def test_unreviewed_plan_rejection():
    services = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(DEPENDENCY_RESPONSE),
            make_response(ENDPOINTS_RESPONSE),
        ]
    )
    analysis = services["notebook_analysis"].analyze(NOTEBOOK)
    services["candidate"].analyze(analysis.analysis_id)
    services["input_schema"].infer(CANDIDATE_ID)
    services["output_schema"].infer(CANDIDATE_ID)
    services["dependency"].analyze(analysis.analysis_id)
    plan = services["plan"].build("nb-1")

    compiler = ScriptedCompiler([CompilerJobResult(job_id="job-1", status="SUCCEEDED")])
    execution_service = LLMCompilationExecutionService(services["plan"], services["review"], compiler)

    with pytest.raises(UnreviewedPlanError):
        execution_service.execute(plan.plan_id)
    assert compiler.calls == 0


def test_unapproved_plan_rejection():
    services, plan = build_reviewed_plan(review_response=BLOCKING_FINDING_RESPONSE)
    compiler = ScriptedCompiler([CompilerJobResult(job_id="job-1", status="SUCCEEDED")])
    execution_service = LLMCompilationExecutionService(services["plan"], services["review"], compiler)

    with pytest.raises(PlanNotApprovedError):
        execution_service.execute(plan.plan_id)
    assert compiler.calls == 0


def test_compiler_failure_propagation():
    services, plan = build_reviewed_plan()
    compiler = ScriptedCompiler([CompilerError("generated code failed to compile", job_id="job-err")])
    execution_service = LLMCompilationExecutionService(services["plan"], services["review"], compiler)

    execution = execution_service.execute(plan.plan_id)

    assert execution.status == "FAILED"
    assert execution.compiler_job_id == "job-err"
    assert execution.completed_at is not None


def test_plan_job_linkage():
    services, plan = build_reviewed_plan()
    compiler = ScriptedCompiler([CompilerJobResult(job_id="job-42", status="SUCCEEDED")])
    execution_service = LLMCompilationExecutionService(services["plan"], services["review"], compiler)

    execution = execution_service.execute(plan.plan_id)

    assert execution_service.status(execution.execution_id) == "SUCCEEDED"
    assert execution_service.compiler_job(execution.execution_id) == "job-42"
    assert execution.plan_id == plan.plan_id


@pytest.mark.parametrize(
    "bad_result",
    [
        {"job_id": "job-1", "status": "SUCCEEDED"},
        CompilerJobResult(job_id="", status="SUCCEEDED"),
        CompilerJobResult(job_id="job-1", status="DONE"),
        CompilerJobResult(job_id="job-1", status="SUCCEEDED", output="not-a-dict"),
    ],
)
def test_invalid_compiler_output_is_rejected(bad_result):
    services, plan = build_reviewed_plan()
    compiler = ScriptedCompiler([bad_result])
    execution_service = LLMCompilationExecutionService(services["plan"], services["review"], compiler)

    with pytest.raises(InvalidCompilerOutputError):
        execution_service.execute(plan.plan_id)

    with pytest.raises(UnknownExecutionError):
        execution_service.status(f"execution-{plan.plan_id}-1")


def test_status_lifecycle():
    services, plan = build_reviewed_plan()
    compiler = ScriptedCompiler(
        [
            CompilerJobResult(job_id="job-ok", status="SUCCEEDED"),
            CompilerError("bad output", job_id="job-bad"),
        ]
    )
    execution_service = LLMCompilationExecutionService(services["plan"], services["review"], compiler)

    succeeded = execution_service.execute(plan.plan_id)
    assert execution_service.status(succeeded.execution_id) == "SUCCEEDED"
    assert succeeded.created_at <= succeeded.completed_at

    failed = execution_service.execute(plan.plan_id)
    assert execution_service.status(failed.execution_id) == "FAILED"
    assert failed.created_at <= failed.completed_at
    assert succeeded.execution_id != failed.execution_id
