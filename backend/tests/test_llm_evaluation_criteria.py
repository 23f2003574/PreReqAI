import pytest

from backend.llm.evaluation_criteria import (
    CriterionAlreadyRegisteredError,
    DuplicateEvaluationCriterionNameError,
    InvalidEvaluationCriterionError,
    LLMEvaluationCriteriaService,
    LLMEvaluationCriterion,
    UnknownEvaluationCriterionError,
)


def make_criterion(**overrides):
    fields = {
        "criterion_id": "criterion-imports-present",
        "name": "imports are present",
        "task_type": "notebook_analysis",
        "description": "the analysis must list every import statement found in the notebook",
        "weight": 1.0,
    }
    fields.update(overrides)
    return LLMEvaluationCriterion(**fields)


def test_register_and_get():
    service = LLMEvaluationCriteriaService()
    criterion = make_criterion()

    registered = service.register(criterion)

    assert registered is criterion
    assert service.get("criterion-imports-present") is criterion

    with pytest.raises(UnknownEvaluationCriterionError):
        service.get("does-not-exist")


def test_duplicate_criterion():
    service = LLMEvaluationCriteriaService()
    service.register(make_criterion())

    with pytest.raises(CriterionAlreadyRegisteredError):
        service.register(make_criterion())

    with pytest.raises(DuplicateEvaluationCriterionNameError):
        service.register(make_criterion(criterion_id="criterion-imports-present-2"))

    # Same name, different task_type: not a duplicate -- criteria are scoped per task_type.
    other_task_type = service.register(
        make_criterion(
            criterion_id="criterion-imports-present-api",
            task_type="api_candidate_detection",
        )
    )
    assert other_task_type.name == "imports are present"


def test_weight_validation():
    with pytest.raises(InvalidEvaluationCriterionError):
        make_criterion(weight=-1).validate()

    with pytest.raises(InvalidEvaluationCriterionError):
        make_criterion(weight="high").validate()

    with pytest.raises(InvalidEvaluationCriterionError):
        make_criterion(weight=True).validate()

    make_criterion(weight=0).validate()
    make_criterion(weight=2.5).validate()


def test_required_optional():
    required_criterion = make_criterion(criterion_id="criterion-required", required=True)
    required_criterion.validate()
    assert required_criterion.required is True

    optional_criterion = make_criterion(criterion_id="criterion-optional")
    optional_criterion.validate()
    assert optional_criterion.required is False

    with pytest.raises(InvalidEvaluationCriterionError):
        make_criterion(required="yes").validate()


def test_task_filtering():
    service = LLMEvaluationCriteriaService()
    notebook_criterion = service.register(make_criterion())
    api_criterion = service.register(
        make_criterion(
            criterion_id="criterion-api-shape",
            name="response is a valid route shape",
            task_type="api_candidate_detection",
        )
    )

    assert service.list() == [api_criterion, notebook_criterion]
    assert service.list(task_type="notebook_analysis") == [notebook_criterion]
    assert service.list(task_type="api_candidate_detection") == [api_criterion]
    assert service.list(task_type="code_transformation") == []


def test_enable_disable():
    service = LLMEvaluationCriteriaService()
    service.register(make_criterion())

    disabled = service.disable("criterion-imports-present")
    assert disabled.enabled is False
    assert service.list() == []

    enabled = service.enable("criterion-imports-present")
    assert enabled.enabled is True
    assert service.list() == [enabled]

    with pytest.raises(UnknownEvaluationCriterionError):
        service.enable("does-not-exist")

    with pytest.raises(UnknownEvaluationCriterionError):
        service.disable("does-not-exist")
