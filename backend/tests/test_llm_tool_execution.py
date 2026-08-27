import dataclasses
import json
import os
import subprocess

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tool_execution import (
    DENIED,
    ExecutionNotSucceededError,
    FAILED,
    InvalidToolHandlerError,
    LLMToolExecutionService,
    REJECTED,
    SUCCEEDED,
    UnknownExecutionError,
)
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tool_validation import LLMToolValidationService
from backend.llm.tools import LLMToolRegistryService, UnknownToolError
from backend.notebook_analysis import LLMNotebookAnalysisService

# ---------------------------------------------------------------------------
# A real project service to execute against, built with the same scripted
# provider harness backend/tests/test_llm_notebook_analysis.py already uses --
# the orchestration stack is real, only the provider is scripted.
# ---------------------------------------------------------------------------


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays one scripted outcome per call."""

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


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "import numpy as np"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
    ],
}

ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": ["import numpy as np"],
        "functions": [{"name": "add", "cell_index": 2}],
        "dependencies": ["numpy"],
    }
)


def build_analysis_service():
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(
            provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True
        )
    )
    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )
    context_service = LLMContextService()
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": ScriptedProvider([LLMResponse(
            content=ANALYSIS_RESPONSE, model="gpt-4o", usage={"total_tokens": 15}
        )])},
    )
    return LLMNotebookAnalysisService(orchestration_service, context_service)


# The tool below exposes LLMNotebookAnalysisService.summary -- a real,
# deterministic project method reading an analysis this project produced.
SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string", "description": "A prior notebook analysis id."},
    },
    "required": ["analysis_id"],
}


def build_stack(enabled=True, wire_invocation_into_permissions=True):
    analysis_service = build_analysis_service()
    analysis = analysis_service.analyze(NOTEBOOK)

    registry = LLMToolRegistryService()
    registry.register(
        "summarize_notebook_analysis",
        "Summarize a notebook analysis via LLMNotebookAnalysisService.summary.",
        SUMMARIZE_SCHEMA,
        enabled=enabled,
    )

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(
        registry, invocation if wire_invocation_into_permissions else None
    )
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", analysis_service.summary)

    return {
        "analysis": analysis,
        "analysis_service": analysis_service,
        "registry": registry,
        "invocation": invocation,
        "permissions": permissions,
        "execution": execution,
    }


def allow(permissions, subject=ANY_SUBJECT, policy_id="allow-1"):
    return permissions.register(
        LLMToolPermissionPolicy(
            policy_id=policy_id,
            tool_name="summarize_notebook_analysis",
            subject=subject,
            allowed=True,
        )
    )


def make_plan(stack, **arguments):
    return stack["invocation"].plan(
        {
            "name": "summarize_notebook_analysis",
            "arguments": arguments or {"analysis_id": stack["analysis"].analysis_id},
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_successful_invocation_through_a_real_project_service():
    stack = build_stack()
    allow(stack["permissions"])
    plan = make_plan(stack)

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == SUCCEEDED
    assert execution.error is None
    assert execution.plan_id == plan.plan_id
    assert execution.tool_name == "summarize_notebook_analysis"

    # The result is what LLMNotebookAnalysisService.summary actually returns.
    expected = stack["analysis_service"].summary(stack["analysis"].analysis_id)
    assert execution.result == expected
    assert execution.result["cell_count"] == 3
    assert execution.result["code_cell_count"] == 2


def test_result_capture():
    stack = build_stack()
    allow(stack["permissions"])
    execution = stack["execution"].execute(make_plan(stack), "user:ada")
    service = stack["execution"]

    assert service.status(execution.execution_id) == SUCCEEDED
    assert service.result(execution.execution_id) == execution.result
    assert service.get(execution.execution_id) == execution
    assert execution.started_at <= execution.completed_at

    with pytest.raises(UnknownExecutionError):
        service.result("does-not-exist")
    with pytest.raises(UnknownExecutionError):
        service.status("does-not-exist")


def test_permission_rejection():
    stack = build_stack()
    # No policy registered at all -- Commit #4 denies by default.
    plan = make_plan(stack)

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == DENIED
    assert execution.result is None
    assert "denied by default" in execution.error

    with pytest.raises(ExecutionNotSucceededError):
        stack["execution"].result(execution.execution_id)


def test_explicit_deny_blocks_execution():
    stack = build_stack()
    allow(stack["permissions"])
    stack["permissions"].register(
        LLMToolPermissionPolicy(
            policy_id="deny-ada",
            tool_name="summarize_notebook_analysis",
            subject="user:ada",
            allowed=False,
        )
    )

    execution = stack["execution"].execute(make_plan(stack), "user:ada")

    assert execution.status == DENIED
    assert "explicitly denies" in execution.error


def test_invalid_arguments_are_rejected_before_planning_completes():
    stack = build_stack()
    allow(stack["permissions"])

    plan = make_plan(stack, wrong_field="x")
    execution = stack["execution"].execute(plan, "user:ada")

    # Commit #3 already rejected the plan; Commit #4 refuses a non-READY plan.
    assert execution.status == DENIED
    assert "REJECTED" in execution.error


def test_arguments_are_revalidated_at_the_execution_boundary():
    """The boundary re-check is the backstop that fires when nothing upstream
    caught a definition that changed after the plan was made."""
    stack = build_stack(wire_invocation_into_permissions=False)
    allow(stack["permissions"])
    plan = make_plan(stack)
    assert stack["execution"].execute(plan, "user:ada").status == SUCCEEDED

    # Tighten the schema after the plan was validated and authorized.
    registry = stack["registry"]
    tool = registry.get("summarize_notebook_analysis")
    registry._tools[tool.tool_id] = dataclasses.replace(
        tool,
        input_schema={
            "type": "object",
            "properties": {
                "analysis_id": {"type": "string"},
                "audience": {"type": "string"},
            },
            "required": ["analysis_id", "audience"],
        },
    )

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == REJECTED
    assert "failed revalidation" in execution.error
    assert "audience" in execution.error


def test_a_stale_plan_is_denied_when_permissions_are_fully_wired():
    """With the Commit #3 service wired into Commit #4, the same staleness is
    caught one gate earlier."""
    stack = build_stack(wire_invocation_into_permissions=True)
    allow(stack["permissions"])
    plan = make_plan(stack)

    registry = stack["registry"]
    tool = registry.get("summarize_notebook_analysis")
    registry._tools[tool.tool_id] = dataclasses.replace(
        tool,
        input_schema={
            "type": "object",
            "properties": {"analysis_id": {"type": "string"}, "audience": {"type": "string"}},
            "required": ["analysis_id", "audience"],
        },
    )

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == DENIED
    assert "no longer valid" in execution.error


def test_disabled_tool():
    stack = build_stack()
    allow(stack["permissions"])
    plan = make_plan(stack)
    stack["registry"].disable("summarize_notebook_analysis")

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == REJECTED
    assert "disabled" in execution.error
    assert execution.result is None


def test_unknown_tool():
    stack = build_stack()
    allow(stack["permissions"])
    plan = make_plan(stack)
    registry = stack["registry"]
    registry._tools.pop(registry._id_by_name.pop("summarize_notebook_analysis"))

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == REJECTED
    assert "not registered" in execution.error


def test_registered_tool_without_a_bound_handler_is_refused():
    stack = build_stack()
    allow(stack["permissions"])
    stack["registry"].register(
        "detect_api_candidates",
        "Identify API-worthy functions via LLMAPICandidateService.",
        {"type": "object", "properties": {"analysis_id": {"type": "string"}}},
    )
    stack["permissions"].register(
        LLMToolPermissionPolicy(
            policy_id="allow-2", tool_name="detect_api_candidates",
            subject=ANY_SUBJECT, allowed=True,
        )
    )
    plan = stack["invocation"].plan(
        {"name": "detect_api_candidates", "arguments": {"analysis_id": "a-1"}}
    )

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == REJECTED
    assert "no bound handler" in execution.error


def test_tool_failure_propagation():
    """A tool that raises is recorded as FAILED, not surfaced as a crash."""
    stack = build_stack()
    allow(stack["permissions"])
    # A real failure from the real service: an analysis_id it does not know.
    plan = make_plan(stack, analysis_id="analysis-does-not-exist")

    execution = stack["execution"].execute(plan, "user:ada")

    assert execution.status == FAILED
    assert execution.result is None
    assert "UnknownAnalysisError" in execution.error

    with pytest.raises(ExecutionNotSucceededError):
        stack["execution"].result(execution.execution_id)


@pytest.mark.parametrize(
    "message",
    [
        "connection refused using api_key=sk-abcdefghijklmnop",
        "auth failed for Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "invalid token: AKIAIOSFODNN7EXAMPLE",
        "password=hunter2-supersecret-value",
    ],
)
def test_secret_safe_error_handling(message):
    """A failing tool must never write a credential into the record."""
    stack = build_stack()
    allow(stack["permissions"])

    def leaky_handler(analysis_id):
        raise RuntimeError(message)

    stack["execution"].bind("summarize_notebook_analysis", leaky_handler)
    execution = stack["execution"].execute(make_plan(stack), "user:ada")

    assert execution.status == FAILED
    assert execution.error == "RuntimeError: [REDACTED]"
    for fragment in ("sk-", "Bearer ", "AKIA", "hunter2"):
        assert fragment not in execution.error


def test_no_traceback_is_stored():
    """Frames carry local variables -- exactly where credentials sit."""
    stack = build_stack()
    allow(stack["permissions"])

    def failing_handler(analysis_id):
        api_key = "sk-thisshouldnevershowup1234"  # noqa: F841  (a frame local)
        raise ValueError("upstream rejected the request")

    stack["execution"].bind("summarize_notebook_analysis", failing_handler)
    execution = stack["execution"].execute(make_plan(stack), "user:ada")

    assert execution.status == FAILED
    assert execution.error == "ValueError: upstream rejected the request"
    assert "Traceback" not in execution.error
    assert "sk-" not in execution.error
    assert "failing_handler" not in execution.error


def test_bind_refuses_shell_and_code_execution_primitives():
    stack = build_stack()
    service = stack["execution"]

    for handler in (eval, exec, compile, __import__, os.system, subprocess.run,
                    subprocess.Popen, os.popen):
        with pytest.raises(InvalidToolHandlerError):
            service.bind("summarize_notebook_analysis", handler)

    with pytest.raises(InvalidToolHandlerError):
        service.bind("summarize_notebook_analysis", "not-callable")

    # The legitimate binding is untouched by the refusals.
    allow(stack["permissions"])
    assert service.execute(make_plan(stack), "user:ada").status == SUCCEEDED


def test_bind_requires_a_registered_tool():
    stack = build_stack()

    with pytest.raises(UnknownToolError):
        stack["execution"].bind("does_not_exist", lambda **kwargs: None)


def test_execute_rejects_a_non_plan():
    stack = build_stack()

    with pytest.raises(TypeError):
        stack["execution"].execute({"name": "summarize_notebook_analysis"}, "user:ada")


def test_execution_does_not_mutate_the_plan_or_registry():
    stack = build_stack()
    allow(stack["permissions"])
    plan = make_plan(stack)
    before = dataclasses.asdict(plan)

    stack["execution"].execute(plan, "user:ada")

    assert dataclasses.asdict(plan) == before
    assert [tool.name for tool in stack["registry"].list()] == [
        "summarize_notebook_analysis"
    ]
    assert stack["registry"].get("summarize_notebook_analysis").enabled is True


def test_executions_listing_and_status_filter():
    stack = build_stack()
    plan = make_plan(stack)
    denied = stack["execution"].execute(plan, "user:ada")
    allow(stack["permissions"])
    succeeded = stack["execution"].execute(make_plan(stack), "user:ada")
    service = stack["execution"]

    assert {e.execution_id for e in service.executions()} == {
        denied.execution_id,
        succeeded.execution_id,
    }
    assert [e.execution_id for e in service.executions(status=SUCCEEDED)] == [
        succeeded.execution_id
    ]
    assert [e.execution_id for e in service.executions(status=DENIED)] == [
        denied.execution_id
    ]


def test_execution_records_are_immutable():
    stack = build_stack()
    allow(stack["permissions"])
    execution = stack["execution"].execute(make_plan(stack), "user:ada")

    with pytest.raises(dataclasses.FrozenInstanceError):
        execution.status = SUCCEEDED


def test_a_custom_validation_service_is_reused_not_reimplemented():
    """The engine defers to the Commit #2 service it was given."""
    stack = build_stack()
    registry = stack["registry"]
    validation = LLMToolValidationService(registry)
    engine = LLMToolExecutionService(registry, stack["permissions"], validation)
    engine.bind("summarize_notebook_analysis", stack["analysis_service"].summary)
    allow(stack["permissions"])

    assert engine.execute(make_plan(stack), "user:ada").status == SUCCEEDED
