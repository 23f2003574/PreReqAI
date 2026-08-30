import pytest

from backend.llm.evaluation_cases import (
    DuplicateEvaluationCaseNameError,
    EvaluationCaseAlreadyRegisteredError,
    InvalidEvaluationCaseError,
    LLMEvaluationCase,
    LLMEvaluationCaseService,
    SecretInInputError,
    UnknownEvaluationCaseError,
)


def make_case(**overrides):
    fields = {
        "case_id": "case-notebook-analysis-1",
        "name": "notebook analysis extracts imports",
        "task_type": "notebook_analysis",
        "input": {
            "notebook_id": "notebook-1",
            "cells": [
                {"index": 0, "cell_type": "code", "source": "import pandas as pd"}
            ],
        },
        "expected_properties": {"imports": ["pandas"]},
    }
    fields.update(overrides)
    return LLMEvaluationCase(**fields)


def test_register_and_get():
    service = LLMEvaluationCaseService()
    case = make_case()

    registered = service.register(case)

    assert registered is case
    assert service.get("case-notebook-analysis-1") is case

    with pytest.raises(UnknownEvaluationCaseError):
        service.get("does-not-exist")


def test_duplicate_case():
    service = LLMEvaluationCaseService()
    service.register(make_case())

    with pytest.raises(EvaluationCaseAlreadyRegisteredError):
        service.register(make_case())

    with pytest.raises(DuplicateEvaluationCaseNameError):
        service.register(make_case(case_id="case-notebook-analysis-2"))


def test_task_validation():
    with pytest.raises(InvalidEvaluationCaseError):
        make_case(task_type="").validate()

    with pytest.raises(InvalidEvaluationCaseError):
        make_case(task_type=None).validate()

    with pytest.raises(InvalidEvaluationCaseError):
        make_case(input="not-a-dict").validate()

    with pytest.raises(InvalidEvaluationCaseError):
        make_case(expected_properties="not-a-dict").validate()

    with pytest.raises(InvalidEvaluationCaseError):
        make_case(expected_properties={}).validate()

    with pytest.raises(InvalidEvaluationCaseError):
        make_case(metadata="not-a-dict").validate()


def test_enable_disable():
    service = LLMEvaluationCaseService()
    service.register(make_case())

    disabled = service.disable("case-notebook-analysis-1")
    assert disabled.enabled is False
    assert service.list() == []

    enabled = service.enable("case-notebook-analysis-1")
    assert enabled.enabled is True
    assert service.list() == [enabled]

    with pytest.raises(UnknownEvaluationCaseError):
        service.enable("does-not-exist")

    with pytest.raises(UnknownEvaluationCaseError):
        service.disable("does-not-exist")


def test_filtering():
    service = LLMEvaluationCaseService()
    notebook_case = service.register(make_case())
    api_case = service.register(
        make_case(
            case_id="case-api-candidate-1",
            name="api candidate detection finds a route",
            task_type="api_candidate_detection",
            input={"function_name": "get_user", "signature": "def get_user(id: int)"},
            expected_properties={"is_candidate": True},
        )
    )
    disabled_case = service.register(
        make_case(
            case_id="case-api-candidate-2",
            name="api candidate detection skips a helper",
            task_type="api_candidate_detection",
            input={"function_name": "_helper", "signature": "def _helper()"},
            expected_properties={"is_candidate": False},
            enabled=False,
        )
    )

    assert service.list() == [api_case, notebook_case]
    assert service.list(task_type="notebook_analysis") == [notebook_case]
    assert service.list(task_type="api_candidate_detection") == [api_case]
    assert disabled_case not in service.list(task_type="api_candidate_detection")
    assert service.list(task_type="code_transformation") == []


def test_secret_rejection():
    service = LLMEvaluationCaseService()

    with pytest.raises(SecretInInputError):
        service.register(
            make_case(
                case_id="case-with-secret",
                name="case carrying a leaked key",
                input={"prompt": "use sk-liveAbCdEfGhIjKlMnOpQrSt to authenticate"},
            )
        )

    with pytest.raises(SecretInInputError):
        service.register(
            make_case(
                case_id="case-with-secret-metadata",
                name="case carrying a leaked key in metadata",
                metadata={"api_key": "AKIAABCDEFGHIJKL1234"},
            )
        )

    assert service.list() == []
