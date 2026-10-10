from .models import InvalidEvaluationCaseError, LLMEvaluationCase


class EvaluationCaseAlreadyRegisteredError(InvalidEvaluationCaseError):
    """Raised when register() is called with a case_id that already exists."""


class DuplicateEvaluationCaseNameError(InvalidEvaluationCaseError):
    """Raised when register() is called with a name already used by another case."""


class UnknownEvaluationCaseError(KeyError):
    """Raised when looking up a case_id that has not been registered."""


class LLMEvaluationCaseService:
    """Registry of LLMEvaluationCase records for measuring LLM behavior.

    Reuses nothing beyond LLMEvaluationCase itself: there is no scoring
    system here and no external evaluation platform -- register() only
    validates and stores a case, and list() is the sole query an evaluator
    would run to find what is currently in scope.
    """

    def __init__(self):
        self._cases = {}
        self._names = set()

    def register(self, case: LLMEvaluationCase) -> LLMEvaluationCase:
        case.validate()

        if case.case_id in self._cases:
            raise EvaluationCaseAlreadyRegisteredError(
                f"case {case.case_id!r} is already registered"
            )
        if case.name in self._names:
            raise DuplicateEvaluationCaseNameError(
                f"case name {case.name!r} is already in use"
            )

        self._cases[case.case_id] = case
        self._names.add(case.name)
        return case

    def get(self, case_id: str) -> LLMEvaluationCase:
        try:
            return self._cases[case_id]
        except KeyError:
            raise UnknownEvaluationCaseError(case_id)

    def list(self, task_type: str = None) -> list:
        """Enabled cases, optionally narrowed to one task_type.

        Disabled cases are never returned here -- this is the query an
        evaluation run would use to decide what to run, and a disabled case
        is explicitly out of scope for that.
        """
        return sorted(
            (
                case
                for case in self._cases.values()
                if case.enabled and (task_type is None or case.task_type == task_type)
            ),
            key=lambda case: case.case_id,
        )

    def enable(self, case_id: str) -> LLMEvaluationCase:
        case = self.get(case_id)
        case.enabled = True
        return case

    def disable(self, case_id: str) -> LLMEvaluationCase:
        case = self.get(case_id)
        case.enabled = False
        return case
