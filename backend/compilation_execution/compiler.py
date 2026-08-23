from abc import ABC, abstractmethod
from dataclasses import dataclass, field


SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
COMPILER_STATUSES = frozenset({SUCCEEDED, FAILED})


@dataclass
class CompilerJobResult:
    """The existing deterministic compiler's own result envelope for one job."""

    job_id: str
    status: str
    output: dict = field(default_factory=dict)


class CompilerError(Exception):
    """Raised by a Compiler implementation for an expected compile-time failure
    (e.g. the generated code doesn't compile) -- anything else the compiler
    raises is treated as an implementation bug, not a compile failure, and
    is allowed to propagate out of the bridge unchanged.
    """

    def __init__(self, message: str, job_id: str = None):
        super().__init__(message)
        self.job_id = job_id


class Compiler(ABC):
    """The existing deterministic compiler's interface, as seen by the bridge.

    No implementation lives in this commit -- this is the contract the real
    compiler already satisfies elsewhere; LLMCompilationExecutionService only
    calls it, it is never re-implemented or bypassed here.
    """

    @abstractmethod
    def compile(self, compiler_input: dict) -> CompilerJobResult:
        """Compile the given job description and return its result, or raise
        CompilerError for an expected compile-time failure."""
