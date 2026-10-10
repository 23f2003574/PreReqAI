import time
from datetime import datetime, timezone

import pytest

from backend.agent_failure_handling import (
    BLOCK,
    CONTINUE,
    DEPENDENCY_FAILURE,
    FAIL,
    LLMAgentFailureService,
    NONE,
    PERMANENT,
    PERMISSION_DENIED,
    RETRY,
    RETRYABLE,
)
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.retry import TransientLLMError
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import LLMToolExecutionService
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_metrics import LLMToolMetricsService
from backend.llm.tool_orchestration import LLMToolCallingOrchestrationService
from backend.llm.tool_permissions import ANY_SUBJECT, LLMToolPermissionPolicy, LLMToolPermissionService
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tool_retry import DEFAULT_POLICY, LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
}


def ok(topic):
    return {"topic": topic, "found": True}


def raises(exc_factory):
    def handler(topic):
        raise exc_factory()

    return handler


def make_slow(delay):
    def handler(topic):
        time.sleep(delay)
        return {"topic": topic, "found": True}

    return handler


class FixedPlanStore:
    def __init__(self, plan: LLMAgentPlan):
        self._plan = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        if plan_id != self._plan.plan_id:
            raise KeyError(plan_id)
        return self._plan


def _step(step_id, tool_name, depends_on=()):
    return LLMAgentPlanStep(
        step_id=step_id,
        action=f"call {tool_name}",
        tool_name=tool_name,
        arguments={"topic": "linear algebra"},
        depends_on=list(depends_on),
        status=READY,
        errors=[],
    )


def _plan(plan_id, steps):
    return LLMAgentPlan(
        plan_id=plan_id, task="a test task", steps=steps, status=READY,
        created_at=datetime.now(timezone.utc),
    )


def build(tools=None, deny_subject_on=None, retry_policy=None):
    tools = tools or {"lookup": ok}

    registry = LLMToolRegistryService()
    for name in tools:
        registry.register(name, f"Tool {name}", SCHEMA)

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
                policy_id=f"deny-{tool_name}-{subject}", tool_name=tool_name, subject=subject, allowed=False
            )
        )

    execution = LLMToolExecutionService(registry, permissions)
    for name, handler in tools.items():
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
    )

    return {
        "registry": registry, "invocation": invocation, "permissions": permissions,
        "orchestrator": orchestrator, "retry": retry,
    }


def wire(stack, plan):
    """Point Commit #2/#3/#9 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    failures = LLMAgentFailureService(store, step_execution, stack["retry"])
    return step_execution, failures


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


def test_retryable_failure():
    stack = build(
        tools={"flaky": raises(lambda: TransientLLMError("upstream is briefly unavailable"))},
        retry_policy=LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
    )
    plan = _plan("plan-1", [_step("step-1", "flaky")])
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    classification = failures.classify("plan-1", "step-1")

    assert classification.category == RETRYABLE
    assert "TransientLLMError" in classification.reason
    assert failures.next_action("plan-1", "step-1") == RETRY
    assert failures.can_continue("plan-1", "step-1") is True


def test_permanent_failure():
    stack = build(
        tools={"broken": raises(lambda: RuntimeError("upstream lookup service is down"))},
        retry_policy=LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
    )
    plan = _plan("plan-1", [_step("step-1", "broken")])
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    classification = failures.classify("plan-1", "step-1")

    assert classification.category == PERMANENT
    assert "RuntimeError" in classification.reason
    assert failures.next_action("plan-1", "step-1") == FAIL
    assert failures.can_continue("plan-1", "step-1") is False


def test_dependency_failure():
    stack = build(tools={"broken": raises(lambda: RuntimeError("x")), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "broken"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    classification = failures.classify("plan-1", "step-2")

    assert classification.category == DEPENDENCY_FAILURE
    assert "step-1" in classification.reason
    assert failures.next_action("plan-1", "step-2") == BLOCK
    assert failures.can_continue("plan-1", "step-2") is False


def test_permission_failure_is_never_retried():
    stack = build(deny_subject_on=("lookup", "user:restricted"))
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:restricted")

    classification = failures.classify("plan-1", "step-1")

    assert classification.category == PERMISSION_DENIED
    assert failures.next_action("plan-1", "step-1") == FAIL
    assert failures.can_continue("plan-1", "step-1") is False


def test_timeout_is_retryable_per_default_policy():
    stack = build(tools={"slow": make_slow(0.2)}, retry_policy=DEFAULT_POLICY)
    plan = _plan("plan-1", [_step("step-1", "slow")])
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada", timeout=0.05)
    time.sleep(0.3)  # let the orphaned worker finish before the pool shuts down

    classification = failures.classify("plan-1", "step-1")

    assert classification.category == RETRYABLE
    assert failures.next_action("plan-1", "step-1") == RETRY


def test_continue_after_a_non_blocking_failure_elsewhere():
    stack = build(tools={"broken": raises(lambda: RuntimeError("x")), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "broken"), _step("step-2", "lookup")])
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    classification = failures.classify("plan-1", "step-2")

    assert classification.category == NONE
    assert failures.next_action("plan-1", "step-2") == CONTINUE
    assert failures.can_continue("plan-1", "step-2") is True


def test_blocking_failure_blocks_every_dependent():
    stack = build(tools={"broken": raises(lambda: RuntimeError("x")), "lookup": ok})
    plan = _plan(
        "plan-1",
        [
            _step("step-1", "broken"),
            _step("step-2", "lookup", depends_on=["step-1"]),
            _step("step-3", "lookup", depends_on=["step-1"]),
        ],
    )
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    assert failures.next_action("plan-1", "step-2") == BLOCK
    assert failures.next_action("plan-1", "step-3") == BLOCK
    assert failures.can_continue("plan-1", "step-2") is False
    assert failures.can_continue("plan-1", "step-3") is False


def test_deterministic_action():
    stack = build(tools={"broken": raises(lambda: RuntimeError("x"))})
    plan = _plan("plan-1", [_step("step-1", "broken")])
    step_execution, failures = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")
    before = stack["registry"].list()
    before_executions = step_execution.executions("plan-1")

    first = failures.classify("plan-1", "step-1")
    second = failures.classify("plan-1", "step-1")

    assert first == second
    assert failures.next_action("plan-1", "step-1") == failures.next_action("plan-1", "step-1")
    assert stack["registry"].list() == before
    assert step_execution.executions("plan-1") == before_executions
