from ..evaluation_cases import LLMEvaluationCaseService
from .models import InvalidEvaluationDatasetError, LLMEvaluationDataset


class CaseTaskTypeMismatchError(InvalidEvaluationDatasetError):
    """Raised when a case's task_type does not match the dataset's task_type."""


class DuplicateCaseInDatasetError(InvalidEvaluationDatasetError):
    """Raised when a case_id is already present in the dataset."""


class UnknownEvaluationDatasetError(KeyError):
    """Raised when looking up a dataset_id that has not been created."""


class CaseNotInDatasetError(KeyError):
    """Raised when remove_case() is called for a case_id not in the dataset."""


class LLMEvaluationDatasetService:
    """Groups Commit #1 cases into reproducible, versioned datasets.

    Reuses Commit #1's LLMEvaluationCaseService as the sole source of case
    identity and task_type -- a dataset only stores an ordered list of
    case_ids, it never copies or re-validates a case's own fields. No
    second dataset framework and no external benchmark platform: cases()
    is the one method a Commit #7-style matrix build would call to fetch
    what to run, and doing so locks the version it read.
    """

    def __init__(self, case_service: LLMEvaluationCaseService):
        self._case_service = case_service
        self._datasets = {}
        self._used_versions = {}
        self._counter = 0

    def _require_case(self, case_id: str, task_type: str):
        case = self._case_service.get(case_id)
        if case.task_type != task_type:
            raise CaseTaskTypeMismatchError(
                f"case {case_id!r} has task_type {case.task_type!r}, expected "
                f"{task_type!r}"
            )
        return case

    def create(self, name: str, task_type: str, case_ids: list) -> LLMEvaluationDataset:
        if not isinstance(case_ids, list):
            raise InvalidEvaluationDatasetError("case_ids must be a list")

        seen = set()
        for case_id in case_ids:
            if case_id in seen:
                raise DuplicateCaseInDatasetError(f"case {case_id!r} is duplicated in case_ids")
            seen.add(case_id)
            self._require_case(case_id, task_type)

        self._counter += 1
        dataset = LLMEvaluationDataset(
            dataset_id=f"eval-dataset-{self._counter}",
            name=name,
            task_type=task_type,
            case_ids=list(case_ids),
            version=1,
        )
        dataset.validate()

        self._datasets[dataset.dataset_id] = dataset
        return dataset

    def get(self, dataset_id: str) -> LLMEvaluationDataset:
        try:
            return self._datasets[dataset_id]
        except KeyError:
            raise UnknownEvaluationDatasetError(dataset_id)

    def _apply(self, dataset_id: str, new_case_ids: list) -> LLMEvaluationDataset:
        dataset = self.get(dataset_id)

        locked = self._used_versions.get(dataset_id) == dataset.version
        new_version = dataset.version + 1 if locked else dataset.version

        updated = LLMEvaluationDataset(
            dataset_id=dataset.dataset_id,
            name=dataset.name,
            task_type=dataset.task_type,
            case_ids=new_case_ids,
            version=new_version,
            enabled=dataset.enabled,
        )
        updated.validate()

        self._datasets[dataset_id] = updated
        return updated

    def add_case(self, dataset_id: str, case_id: str) -> LLMEvaluationDataset:
        dataset = self.get(dataset_id)
        if case_id in dataset.case_ids:
            raise DuplicateCaseInDatasetError(
                f"case {case_id!r} is already in dataset {dataset_id!r}"
            )
        self._require_case(case_id, dataset.task_type)

        return self._apply(dataset_id, dataset.case_ids + [case_id])

    def remove_case(self, dataset_id: str, case_id: str) -> LLMEvaluationDataset:
        dataset = self.get(dataset_id)
        if case_id not in dataset.case_ids:
            raise CaseNotInDatasetError(case_id)

        return self._apply(dataset_id, [c for c in dataset.case_ids if c != case_id])

    def cases(self, dataset_id: str) -> list:
        """The dataset's cases, in order, excluding any now-disabled case.

        Reading this locks dataset.version: a later add_case/remove_case on
        this dataset_id will produce a new version rather than mutating the
        one just read.
        """
        dataset = self.get(dataset_id)
        self._used_versions[dataset_id] = dataset.version

        resolved = [self._case_service.get(case_id) for case_id in dataset.case_ids]
        return [case for case in resolved if case.enabled]
