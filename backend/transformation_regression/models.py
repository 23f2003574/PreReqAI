from dataclasses import dataclass
from datetime import datetime

CRITICAL = "CRITICAL"
MINOR = "MINOR"
SEVERITIES = frozenset({CRITICAL, MINOR})


@dataclass(frozen=True)
class LLMTransformationRegression:
    """One detected behavioral difference between a function's pre- and
    post-transformation execution, for a single backend.test_generation test.

    expected/actual are each {"raised", "value", "error"} dicts -- expected
    is what the pre-transformation (original_source) function actually
    produced for test.input, actual is what the post-transformation
    (applied_source) function actually produced for the same input.
    severity is CRITICAL for a VALID/EDGE test (the call was always
    supposed to succeed the same way) and MINOR for an INVALID test whose
    raised/didn't-raise outcome changed. Detecting this never mutates
    notebook source, the execution, or anything upstream of it, and never
    fixes the regression itself -- see
    LLMTransformationRegressionService.resolve().
    """

    regression_id: str
    execution_id: str
    test_id: str
    expected: dict
    actual: dict
    severity: str
    detected_at: datetime
