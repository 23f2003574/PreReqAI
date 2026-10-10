from .models import InvalidEvaluationCriterionError, LLMEvaluationCriterion


class CriterionAlreadyRegisteredError(InvalidEvaluationCriterionError):
    """Raised when register() is called with a criterion_id that already exists."""


class DuplicateEvaluationCriterionNameError(InvalidEvaluationCriterionError):
    """Raised when a criterion name is already used by another criterion in the same task_type."""


class UnknownEvaluationCriterionError(KeyError):
    """Raised when looking up a criterion_id that has not been registered."""


class LLMEvaluationCriteriaService:
    """Registry of LLMEvaluationCriterion records, independent of any provider/model.

    Reuses nothing beyond LLMEvaluationCriterion itself -- the same shape as
    Commit #1's LLMEvaluationCaseService: no scoring, no external evaluation
    service, only registration, lookup, and the task_type-scoped uniqueness
    a criterion needs before Commit #1/#2's cases and runs can be judged
    against it.
    """

    def __init__(self):
        self._criteria = {}
        self._names_by_task_type = {}

    def validate(self, criterion: LLMEvaluationCriterion) -> bool:
        """Structural validation plus registry-aware name uniqueness, without registering."""
        criterion.validate()

        existing_id = self._names_by_task_type.get(criterion.task_type, {}).get(criterion.name)
        if existing_id is not None and existing_id != criterion.criterion_id:
            raise DuplicateEvaluationCriterionNameError(
                f"criterion name {criterion.name!r} is already registered for "
                f"task_type {criterion.task_type!r}"
            )
        return True

    def register(self, criterion: LLMEvaluationCriterion) -> LLMEvaluationCriterion:
        self.validate(criterion)

        if criterion.criterion_id in self._criteria:
            raise CriterionAlreadyRegisteredError(
                f"criterion {criterion.criterion_id!r} is already registered"
            )

        self._criteria[criterion.criterion_id] = criterion
        self._names_by_task_type.setdefault(criterion.task_type, {})[
            criterion.name
        ] = criterion.criterion_id
        return criterion

    def get(self, criterion_id: str) -> LLMEvaluationCriterion:
        try:
            return self._criteria[criterion_id]
        except KeyError:
            raise UnknownEvaluationCriterionError(criterion_id)

    def list(self, task_type: str = None) -> list:
        """Enabled criteria, optionally narrowed to one task_type.

        Disabled criteria are never returned here, the same way a disabled
        Commit #1 case is excluded from its own list().
        """
        return sorted(
            (
                criterion
                for criterion in self._criteria.values()
                if criterion.enabled and (task_type is None or criterion.task_type == task_type)
            ),
            key=lambda criterion: criterion.criterion_id,
        )

    def enable(self, criterion_id: str) -> LLMEvaluationCriterion:
        criterion = self.get(criterion_id)
        criterion.enabled = True
        return criterion

    def disable(self, criterion_id: str) -> LLMEvaluationCriterion:
        criterion = self.get(criterion_id)
        criterion.enabled = False
        return criterion
