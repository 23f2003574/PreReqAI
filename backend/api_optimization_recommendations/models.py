from dataclasses import dataclass

COMPUTE = "COMPUTE"
IO = "IO"
DEPENDENCY = "DEPENDENCY"
SCHEMA = "SCHEMA"
CODE = "CODE"
CATEGORIES = frozenset({COMPUTE, IO, DEPENDENCY, SCHEMA, CODE})

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
IMPACT_LEVELS = frozenset({LOW, MEDIUM, HIGH})


@dataclass(frozen=True)
class LLMAPIOptimization:
    """One LLM-proposed, evidence-backed optimization for a Commit #4
    recommendation's endpoint -- inert, never applied automatically.

    Never proposed for an endpoint with an unresolved Commit #8 blocking
    risk finding (see LLMAPIOptimizationService.analyze()/validate()) --
    optimizing something with a known blocking risk is premature.
    rationale is the required evidence for the claimed improvement;
    expected_impact is LOW/MEDIUM/HIGH. This service never modifies
    notebook source or generated API code -- it only ever proposes what a
    human might choose to apply.
    """

    optimization_id: str
    endpoint: str
    category: str
    recommendation: str
    rationale: str
    expected_impact: str
    confidence: float
