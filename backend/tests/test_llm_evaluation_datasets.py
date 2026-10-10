import pytest

from backend.llm.evaluation_cases import LLMEvaluationCase, LLMEvaluationCaseService, UnknownEvaluationCaseError
from backend.llm.evaluation_datasets import (
    CaseNotInDatasetError,
    CaseTaskTypeMismatchError,
    DuplicateCaseInDatasetError,
    LLMEvaluationDatasetService,
    UnknownEvaluationDatasetError,
)


def make_case(case_id, **overrides):
    fields = {
        "case_id": case_id,
        "name": f"case {case_id}",
        "task_type": "notebook_analysis",
        "input": {"notebook_id": case_id, "cells": [{"index": 0, "cell_type": "code", "source": "import pandas"}]},
        "expected_properties": {"imports": ["pandas"]},
    }
    fields.update(overrides)
    return LLMEvaluationCase(**fields)


def build_env():
    case_service = LLMEvaluationCaseService()
    dataset_service = LLMEvaluationDatasetService(case_service)
    return case_service, dataset_service


def test_dataset_creation():
    case_service, dataset_service = build_env()
    case_service.register(make_case("case-a"))
    case_service.register(make_case("case-b"))

    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a", "case-b"])

    assert dataset.task_type == "notebook_analysis"
    assert dataset.case_ids == ["case-a", "case-b"]
    assert dataset.version == 1
    assert dataset.enabled is True
    assert dataset_service.get(dataset.dataset_id) is dataset

    with pytest.raises(UnknownEvaluationDatasetError):
        dataset_service.get("does-not-exist")


def test_case_validation():
    case_service, dataset_service = build_env()
    case_service.register(make_case("case-a"))

    with pytest.raises(UnknownEvaluationCaseError):
        dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a", "does-not-exist"])

    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a"])

    with pytest.raises(UnknownEvaluationCaseError):
        dataset_service.add_case(dataset.dataset_id, "does-not-exist")


def test_task_mismatch():
    case_service, dataset_service = build_env()
    case_service.register(make_case("case-a"))
    case_service.register(make_case("case-api", task_type="api_candidate_detection"))

    with pytest.raises(CaseTaskTypeMismatchError):
        dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a", "case-api"])

    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a"])

    with pytest.raises(CaseTaskTypeMismatchError):
        dataset_service.add_case(dataset.dataset_id, "case-api")


def test_duplicate_case():
    case_service, dataset_service = build_env()
    case_service.register(make_case("case-a"))

    with pytest.raises(DuplicateCaseInDatasetError):
        dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a", "case-a"])

    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a"])

    with pytest.raises(DuplicateCaseInDatasetError):
        dataset_service.add_case(dataset.dataset_id, "case-a")


def test_ordering():
    case_service, dataset_service = build_env()
    for case_id in ("case-b", "case-a", "case-c"):
        case_service.register(make_case(case_id))

    dataset = dataset_service.create(
        "notebook benchmark", "notebook_analysis", ["case-b", "case-a", "case-c"]
    )
    assert dataset.case_ids == ["case-b", "case-a", "case-c"]

    case_service.register(make_case("case-d"))
    dataset = dataset_service.add_case(dataset.dataset_id, "case-d")
    assert dataset.case_ids == ["case-b", "case-a", "case-c", "case-d"]

    dataset = dataset_service.remove_case(dataset.dataset_id, "case-a")
    assert dataset.case_ids == ["case-b", "case-c", "case-d"]

    with pytest.raises(CaseNotInDatasetError):
        dataset_service.remove_case(dataset.dataset_id, "case-a")


def test_version_immutability():
    case_service, dataset_service = build_env()
    for case_id in ("case-a", "case-b", "case-c"):
        case_service.register(make_case(case_id))

    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a"])
    assert dataset.version == 1

    # Mutating before this version has ever been used keeps it in place.
    dataset = dataset_service.add_case(dataset.dataset_id, "case-b")
    assert dataset.version == 1
    assert dataset.case_ids == ["case-a", "case-b"]

    # Reading cases() locks version 1 -- a benchmark run would have used it.
    used = dataset_service.cases(dataset.dataset_id)
    assert [case.case_id for case in used] == ["case-a", "case-b"]

    dataset = dataset_service.add_case(dataset.dataset_id, "case-c")
    assert dataset.version == 2
    assert dataset.case_ids == ["case-a", "case-b", "case-c"]

    # Version 2 has not been used yet, so this mutation stays on version 2.
    dataset = dataset_service.remove_case(dataset.dataset_id, "case-c")
    assert dataset.version == 2
    assert dataset.case_ids == ["case-a", "case-b"]

    dataset_service.cases(dataset.dataset_id)
    dataset = dataset_service.remove_case(dataset.dataset_id, "case-b")
    assert dataset.version == 3
    assert dataset.case_ids == ["case-a"]


def test_disabled_case_handling():
    case_service, dataset_service = build_env()
    case_service.register(make_case("case-a"))
    case_service.register(make_case("case-b"))

    dataset = dataset_service.create("notebook benchmark", "notebook_analysis", ["case-a", "case-b"])

    case_service.disable("case-b")
    active = dataset_service.cases(dataset.dataset_id)
    assert [case.case_id for case in active] == ["case-a"]

    # Disabled cases stay in the dataset's own ordering -- only excluded from
    # what cases() hands back for a new evaluation.
    assert dataset_service.get(dataset.dataset_id).case_ids == ["case-a", "case-b"]

    case_service.enable("case-b")
    active_again = dataset_service.cases(dataset.dataset_id)
    assert [case.case_id for case in active_again] == ["case-a", "case-b"]
