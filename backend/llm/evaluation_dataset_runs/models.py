from dataclasses import dataclass
from datetime import datetime

COMPLETED = "COMPLETED"
DATASET_RUN_STATUSES = frozenset({COMPLETED})


class InvalidEvaluationDatasetRunError(ValueError):
    """Raised when an LLMEvaluationDatasetRun fails validation."""


@dataclass(frozen=True)
class LLMEvaluationDatasetRun:
    """One reproducible pass of a Commit #8 dataset through a fixed provider/model.

    case_runs is the Commit #2 run_id for every eligible (enabled) case in
    the dataset, in the dataset's own order -- one entry per case, always,
    whether that individual run succeeded or failed. A case's failure is
    never dropped from case_runs: it stays recorded as a FAILED run_id, the
    same way Commit #2 itself never discards a failed run. provider/model
    are exactly what this dataset run was executed with, never inferred
    after the fact.
    """

    dataset_run_id: str
    dataset_id: str
    provider: str
    model: str
    case_runs: list
    status: str
    started_at: datetime
    completed_at: datetime

    def validate(self):
        if not self.dataset_run_id or not isinstance(self.dataset_run_id, str):
            raise InvalidEvaluationDatasetRunError("dataset_run_id is required")

        if not self.dataset_id or not isinstance(self.dataset_id, str):
            raise InvalidEvaluationDatasetRunError("dataset_id is required")

        if not self.provider or not isinstance(self.provider, str):
            raise InvalidEvaluationDatasetRunError("provider is required")

        if not self.model or not isinstance(self.model, str):
            raise InvalidEvaluationDatasetRunError("model is required")

        if not isinstance(self.case_runs, list):
            raise InvalidEvaluationDatasetRunError("case_runs must be a list")

        if self.status not in DATASET_RUN_STATUSES:
            raise InvalidEvaluationDatasetRunError(
                f"status must be one of {sorted(DATASET_RUN_STATUSES)}"
            )

        if not isinstance(self.started_at, datetime) or not isinstance(self.completed_at, datetime):
            raise InvalidEvaluationDatasetRunError("started_at/completed_at must be datetimes")
