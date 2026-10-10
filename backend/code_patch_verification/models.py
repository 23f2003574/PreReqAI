from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMCodePatchVerification:
    """The outcome of verifying one applied Commit #5 execution before its
    patched generated output may be accepted as valid.

    findings is a list of {"category", "target", "message", "blocking"}
    dicts. syntax_valid reflects the first, blocking check (every
    "source"-holding key in the current generated output must still
    parse). tests_passed reflects whether backend.generated_code_review's
    own existing review pipeline -- run again against the current,
    already-patched output -- no longer reports any blocking finding; this
    is the "relevant existing/generated test" for generated output, the
    same way backend.transformation_verification reuses the original
    notebook-to-API series' own generated tests for notebook cells. Syntax
    is always checked first, with the re-review skipped entirely if syntax
    fails. Producing this record never modifies the generated output, the
    execution, or anything upstream of it.
    """

    verification_id: str
    execution_id: str
    syntax_valid: bool
    tests_passed: bool
    findings: list
    verified_at: datetime
