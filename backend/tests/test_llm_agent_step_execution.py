import time
from datetime import datetime, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import (
    LLMAgentExecutionService,
    StepNotSucceededError,
    UnknownAgentStepError,
    UnknownAgentStepExecutionError,
)
from backend.agent_task_planning import (
    READY,
    LLMAgentPlan,
    LLMAgentPlanningService,
    LLMAgentPlanStep,
)
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.retry import TransientLLMError
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import (
    DENIED,
    FAILED,
    LLMToolExecutionService,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
)
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_metrics import LLMToolMetricsService
from backend.llm.tool_orchestration import LLMToolCallingOrchestrationService
from backend.llm.tool_permissions import ANY_SUBJECT, LLMToolPermissionPolicy, LLMToolPermissionService
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService

FETCH_SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
}

SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {"notes": {"type": "string"}},
    "required": ["notes"],
}

PREREQUISITES = {"linear algebra": ["arithmetic", "basic algebra"]}


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


def fetch_prerequisites(topic):
    return {"prerequisites": PREREQUISITES.get(topic, [])}


def always_fails(topic):
    raise RuntimeError("upstream lookup service is down")


class FixedPlanStore:
    """A minimal stand-in for LLMAgentPlanningService exposing only get().

    Lets a test construct exactly the step/dependency shape it needs
    (an unmet dependency, a failed one, a step naming a slow or failing
    tool) without needing a scripted LLM response for every scenario --
    the same technique Commit #2's own tests use.
    """

    def __init__(self, plan: LLMAgentPlan):
        self._plan = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        if plan_id != self._plan.plan_id:
            raise KeyError(plan_id)
        return self._plan


def _step(step_id, tool_name, depends_on=(), arguments=None, status=READY, errors=()):
    return LLMAgentPlanStep(
        step_id=step_id,
        action=f"call {tool_name}",
        tool_name=tool_name,
        arguments=arguments or {"topic": "linear algebra"},
        depends_on=list(depends_on),
        status=status,
        errors=list(errors),
    )


def _plan(plan_id, steps, status=READY):
    return LLMAgentPlan(
        plan_id=plan_id, task="a test task", steps=steps, status=status,
        created_at=datetime.now(timezone.utc),
    )


def build(tools=None, deny_subject_on=None, timeout=None, retry_policy=None):
    """Wires the full existing tool-calling pipeline (Commits #1-#13 of the
    tool-calling chain) exactly as backend.tests.test_llm_tool_calling_orchestration
    does, then puts Commit #1/#2's planning/validation services and the new
    LLMAgentExecutionService in front of it. `tools` is {name: (schema, handler)}.
    """
    tools = tools or {"fetch_prerequisites": (FETCH_SCHEMA, fetch_prerequisites)}

    registry = LLMToolRegistryService()
    for name, (schema, _handler) in tools.items():
        registry.register(name, f"Tool {name}", schema)

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    for index, name in enumerate(tools):
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id=f"allow-{name}-{index}", tool_name=name, subject=ANY_SUBJECT, allowed=True
            )
        )
    if deny_subject_on is not None:
        tool_name, subject = deny_subject_on
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id=f"deny-{tool_name}-{subject}",
                tool_name=tool_name,
                subject=subject,
                allowed=False,
            )
        )

    execution = LLMToolExecutionService(registry, permissions)
    for name, (_schema, handler) in tools.items():
        execution.bind(name, handler)

    idempotency = LLMToolIdempotencyService(execution, permissions)
    control = LLMToolExecutionControlService(execution, idempotency)
    retry = LLMToolRetryService(
        control, execution, retry_policy or LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
        sleeper=lambda seconds: None, idempotency_service=idempotency,
    )
    audit = LLMToolAuditService()
    metrics = LLMToolMetricsService(retry)
    results = LLMToolResultService()

    orchestrator = LLMToolCallingOrchestrationService(
        invocation_service=invocation,
        permission_service=permissions,
        execution_service=execution,
        result_service=results,
        idempotency_service=idempotency,
        control_service=control,
        retry_service=retry,
        audit_service=audit,
        metrics_service=metrics,
        default_timeout=timeout,
    )

    llm_config = LLMProviderConfigService()
    llm_config.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )
    routing = LLMModelRoutingService(llm_config)
    routing.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )
    context_service = LLMContextService()
    llm_provider = ScriptedProvider([])
    llm_orchestration = LLMRequestOrchestrationService(
        context_service=context_service, routing_service=routing, providers={"openai": llm_provider},
    )
    planning_service = LLMAgentPlanningService(registry, llm_orchestration, context_service)
    validation_service = LLMAgentPlanValidationService(
        planning_service, registry, permissions, invocation_service=invocation
    )

    agent_execution = LLMAgentExecutionService(planning_service, validation_service, orchestrator)

    return {
        "registry": registry,
        "invocation": invocation,
        "permissions": permissions,
        "control": control,
        "orchestrator": orchestrator,
        "planning_service": planning_service,
        "validation_service": validation_service,
        "agent_execution": agent_execution,
    }


def register_plan(stack, plan, permission_service=None):
    """Point the stack's Commit #1/#2/#3 services at a directly-built plan."""
    store = FixedPlanStore(plan)
    stack["planning_service"] = store
    stack["validation_service"] = LLMAgentPlanValidationService(
        store,
        stack["registry"],
        permission_service or stack["permissions"],
        invocation_service=stack["invocation"],
    )
    stack["agent_execution"] = LLMAgentExecutionService(
        store, stack["validation_service"], stack["orchestrator"]
    )
    return stack


@pytest.fixture(autouse=True)
def _shutdown_pools():
    created = []
    original = LLMToolExecutionControlService.__init__

    def tracking_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        created.append(self)

    LLMToolExecutionControlService.__init__ = tracking_init
    try:
        yield
    finally:
        LLMToolExecutionControlService.__init__ = original
        for service in created:
            service.shutdown(wait=False)


def test_successful_step_execution():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "fetch_prerequisites")])
    register_plan(stack, plan)

    execution = stack["agent_execution"].execute_step("plan-1", "step-1", "user:ada")

    assert execution.status == SUCCEEDED
    assert execution.error is None
    assert execution.result.output == {"prerequisites": ["arithmetic", "basic algebra"]}
    assert stack["agent_execution"].status(execution.execution_id) == SUCCEEDED
    assert stack["agent_execution"].result(execution.execution_id) is execution.result


def test_result_capture_is_retrievable_after_the_fact():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "fetch_prerequisites")])
    register_plan(stack, plan)

    execution = stack["agent_execution"].execute_step("plan-1", "step-1", "user:ada")
    fetched = stack["agent_execution"].get(execution.execution_id)

    assert fetched == execution
    assert stack["agent_execution"].result(execution.execution_id).output == {
        "prerequisites": ["arithmetic", "basic algebra"]
    }


def test_invalid_plan_is_rejected_before_any_tool_call():
    stack = build()
    # A step naming a tool that was never registered fails Commit #2
    # validation, so the whole plan must never reach the tool-calling
    # pipeline.
    plan = _plan("plan-1", [_step("step-1", "no_such_tool")])
    register_plan(stack, plan)

    execution = stack["agent_execution"].execute_step("plan-1", "step-1", "user:ada")

    assert execution.status == REJECTED
    assert "failed validation" in execution.error
    assert execution.result is None


def test_unmet_dependency_blocks_execution():
    stack = build()
    plan = _plan(
        "plan-1",
        [
            _step("step-1", "fetch_prerequisites"),
            _step("step-2", "fetch_prerequisites", depends_on=["step-1"]),
        ],
    )
    register_plan(stack, plan)

    # step-2 is attempted first: step-1 has not been executed at all yet.
    execution = stack["agent_execution"].execute_step("plan-1", "step-2", "user:ada")

    assert execution.status == REJECTED
    assert "has not been executed yet" in execution.error


def test_dependency_failure_blocks_the_dependent_step():
    stack = build(tools={"flaky_tool": (FETCH_SCHEMA, always_fails)})
    plan = _plan(
        "plan-1",
        [
            _step("step-1", "flaky_tool"),
            _step("step-2", "flaky_tool", depends_on=["step-1"]),
        ],
    )
    register_plan(stack, plan)

    first = stack["agent_execution"].execute_step("plan-1", "step-1", "user:ada")
    assert first.status == FAILED

    second = stack["agent_execution"].execute_step("plan-1", "step-2", "user:ada")

    assert second.status == REJECTED
    assert "did not succeed" in second.error
    assert "FAILED" in second.error


def test_permission_rejection_produces_a_denied_status():
    stack = build(deny_subject_on=("fetch_prerequisites", "user:restricted"))
    plan = _plan("plan-1", [_step("step-1", "fetch_prerequisites")])
    register_plan(stack, plan)

    # Commit #2 validation (checked against ANY_SUBJECT by default) still
    # passes -- the tool is usable by subjects in general. It is only this
    # specific subject that Commit #4 authorization denies at execution.
    assert stack["validation_service"].blocking("plan-1") is False

    execution = stack["agent_execution"].execute_step("plan-1", "step-1", "user:restricted")

    assert execution.status == DENIED
    assert execution.result is None
    assert execution.error is not None


def test_tool_failure_is_recorded_as_failed_not_successful():
    stack = build(tools={"flaky_tool": (FETCH_SCHEMA, always_fails)})
    plan = _plan("plan-1", [_step("step-1", "flaky_tool")])
    register_plan(stack, plan)

    execution = stack["agent_execution"].execute_step("plan-1", "step-1", "user:ada")

    assert execution.status == FAILED
    assert execution.result is None
    assert "upstream lookup service is down" in execution.error

    try:
        stack["agent_execution"].result(execution.execution_id)
        assert False, "expected StepNotSucceededError"
    except StepNotSucceededError:
        pass


def test_timeout_is_enforced():
    def slow(topic):
        time.sleep(0.4)
        return {"prerequisites": []}

    stack = build(
        tools={"slow_tool": (FETCH_SCHEMA, slow)},
        retry_policy=LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
    )
    plan = _plan("plan-1", [_step("step-1", "slow_tool")])
    register_plan(stack, plan)

    execution = stack["agent_execution"].execute_step(
        "plan-1", "step-1", "user:ada", timeout=0.05
    )

    assert execution.status == TIMED_OUT
    assert execution.result is None
    time.sleep(0.6)  # let the orphaned worker finish before the pool shuts down


def test_unknown_plan_raises():
    stack = build()
    try:
        stack["agent_execution"].execute_step("no-such-plan", "step-1", "user:ada")
        assert False, "expected an error for an unknown plan"
    except KeyError:
        pass


def test_unknown_step_raises():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "fetch_prerequisites")])
    register_plan(stack, plan)

    try:
        stack["agent_execution"].execute_step("plan-1", "no-such-step", "user:ada")
        assert False, "expected UnknownAgentStepError"
    except UnknownAgentStepError:
        pass


def test_unknown_execution_id_raises():
    stack = build()
    try:
        stack["agent_execution"].status("no-such-execution")
        assert False, "expected UnknownAgentStepExecutionError"
    except UnknownAgentStepExecutionError:
        pass


def test_execution_never_runs_a_second_engine_or_mutates_the_registry():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "fetch_prerequisites")])
    register_plan(stack, plan)
    before = stack["registry"].list()

    stack["agent_execution"].execute_step("plan-1", "step-1", "user:ada")

    assert stack["registry"].list() == before
