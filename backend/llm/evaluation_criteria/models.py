from dataclasses import dataclass


class InvalidEvaluationCriterionError(ValueError):
    """Raised when an LLMEvaluationCriterion fails validation."""


@dataclass
class LLMEvaluationCriterion:
    """One structured, provider-agnostic criterion for judging an LLM output.

    Reuses Commit #1's task_type vocabulary: task_type names the same real
    project capability an LLMEvaluationCase.task_type would name, so a
    criterion is registered against exactly the same surface ("notebook_
    analysis", "api_candidate_detection", ...) Commit #1 cases already use.
    weight and required describe how a future scorer should weigh this
    criterion; nothing here scores anything -- a criterion only says what
    an output should be judged on, never how, and never against which
    provider or model produced it.
    """

    criterion_id: str
    name: str
    task_type: str
    description: str
    weight: float
    required: bool = False
    enabled: bool = True

    def validate(self):
        if not self.criterion_id or not isinstance(self.criterion_id, str):
            raise InvalidEvaluationCriterionError("criterion_id is required")

        if not self.name or not isinstance(self.name, str):
            raise InvalidEvaluationCriterionError("name is required")

        if not self.task_type or not isinstance(self.task_type, str):
            raise InvalidEvaluationCriterionError("task_type is required")

        if not self.description or not isinstance(self.description, str):
            raise InvalidEvaluationCriterionError("description is required")

        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise InvalidEvaluationCriterionError("weight must be a number")
        if self.weight < 0:
            raise InvalidEvaluationCriterionError("weight must be non-negative")

        if not isinstance(self.required, bool):
            raise InvalidEvaluationCriterionError("required must be a bool")

        if not isinstance(self.enabled, bool):
            raise InvalidEvaluationCriterionError("enabled must be a bool")
