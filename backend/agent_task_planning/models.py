from dataclasses import dataclass
from datetime import datetime

READY = "READY"
REJECTED = "REJECTED"
STATUSES = frozenset({READY, REJECTED})


@dataclass(frozen=True)
class LLMAgentPlanStep:
    """One step of a multi-step LLMAgentPlan.

    tool_name must name a tool currently registered (and enabled) in the
    existing backend.llm.tools.LLMToolRegistryService -- a step can never
    propose a capability the project does not actually expose. depends_on
    lists the step_ids (within the same plan) that must complete before
    this step may run; planning only checks that every referenced id
    exists and that no cycle results, it never runs anything. status is
    READY only when the tool exists, is enabled, and every dependency is
    valid; otherwise REJECTED, with errors explaining why (empty when
    READY).
    """

    step_id: str
    action: str
    tool_name: str
    arguments: dict
    depends_on: list
    status: str
    errors: list


@dataclass(frozen=True)
class LLMAgentPlan:
    """A structured, reviewable multi-step plan for accomplishing one task.

    steps is a list of LLMAgentPlanStep, in the order the model proposed
    them. status is READY only when every step is READY; a plan with any
    REJECTED step is REJECTED as a whole, since a plan that depends on an
    unavailable capability cannot be carried out as proposed. A plan is
    never executed -- create()/validate()/preview() only produce and
    inspect the proposal.
    """

    plan_id: str
    task: str
    steps: list
    status: str
    created_at: datetime
