from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType


ENDPOINT_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class LLMCompilationPlan:
    """A validated, deterministic plan the compiler can consume directly.

    Immutable by construction: candidates/dependencies/endpoints are tuples
    and schemas/validations are read-only MappingProxyType views, so nothing
    -- not even LLMCompilationPlanningService itself -- can mutate a plan
    once build() returns it. validate() only ever reads a plan, never writes
    to it.
    """

    plan_id: str
    notebook_id: str
    candidates: tuple
    schemas: MappingProxyType
    dependencies: tuple
    endpoints: tuple
    validations: MappingProxyType
    generated_at: datetime
