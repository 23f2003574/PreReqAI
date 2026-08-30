from dataclasses import dataclass


class InvalidEvaluationDatasetError(ValueError):
    """Raised when an LLMEvaluationDataset fails validation."""


@dataclass
class LLMEvaluationDataset:
    """A reproducible, ordered collection of Commit #1 cases for one task_type.

    case_ids is ordered and never carries a duplicate. version starts at 1
    and only ever increases -- once a version has been read by cases() (the
    same call a benchmark run would use to fetch what to execute), that
    exact case_ids/version pairing is never mutated in place; a further
    add_case/remove_case instead produces the next version.
    """

    dataset_id: str
    name: str
    task_type: str
    case_ids: list
    version: int
    enabled: bool = True

    def validate(self):
        if not self.dataset_id or not isinstance(self.dataset_id, str):
            raise InvalidEvaluationDatasetError("dataset_id is required")

        if not self.name or not isinstance(self.name, str):
            raise InvalidEvaluationDatasetError("name is required")

        if not self.task_type or not isinstance(self.task_type, str):
            raise InvalidEvaluationDatasetError("task_type is required")

        if not isinstance(self.case_ids, list):
            raise InvalidEvaluationDatasetError("case_ids must be a list")
        if len(set(self.case_ids)) != len(self.case_ids):
            raise InvalidEvaluationDatasetError("case_ids must not contain duplicates")

        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise InvalidEvaluationDatasetError("version must be a positive integer")

        if not isinstance(self.enabled, bool):
            raise InvalidEvaluationDatasetError("enabled must be a bool")
