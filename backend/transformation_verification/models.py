from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMTransformationVerification:
    """The outcome of verifying one applied Commit #5 execution before it is
    accepted as a valid build input.

    findings is a list of {"category", "target", "message", "blocking"}
    dicts. syntax_valid reflects Commit #6's first, blocking check (every
    applied cell must still parse); tests_passed reflects whether every
    generated test (backend.test_generation, from the original
    notebook-to-API series) still matches the transformed function's
    parameter signature -- both are checked deterministically and syntax is
    always checked first, with tests skipped entirely if syntax fails.
    Producing this record never modifies notebook source, the execution, or
    anything upstream of it.
    """

    verification_id: str
    execution_id: str
    syntax_valid: bool
    tests_passed: bool
    findings: list
    verified_at: datetime
