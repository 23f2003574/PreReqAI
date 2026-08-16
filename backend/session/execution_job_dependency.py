from dataclasses import (
    dataclass,
)

from .execution_job_dependency_error import (
    ExecutionJobDependencyError,
)

STATUS_SUCCEEDED = "SUCCEEDED"


@dataclass(frozen=True)
class ExecutionJobDependency:
    """
    Immutable record that one execution job may not run until another
    reaches a required status.

    The dependency is a value object only. It performs no readiness
    evaluation or cycle detection of its own; adding, removing, and
    evaluating dependencies is the responsibility of an execution job
    dependency service.

    Attributes:
        job_id: The identifier of the job that is blocked
        depends_on: The identifier of the job that must reach
            required_status before job_id may run
        required_status: The status depends_on must reach for this
            dependency to be considered satisfied. Defaults to
            STATUS_SUCCEEDED
    """

    job_id: str

    depends_on: str

    required_status: str = STATUS_SUCCEEDED

    def __post_init__(self):
        self._require_text(self.job_id, "job ID")
        self._require_text(self.depends_on, "depends_on job ID")
        self._require_text(self.required_status, "required status")

        if self.job_id == self.depends_on:
            raise ExecutionJobDependencyError(
                f"Cannot build an execution job dependency: job ID {self.job_id!r} cannot depend on itself."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionJobDependencyError(
                f"Cannot build an execution job dependency with an empty or blank {field_name}."
            )
