"""ARCHITECTURE.md quotes the registry and rule counts; they must match the code."""
import re
from pathlib import Path

import pytest

from backend.concepts.concept_registry import ConceptRegistry
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.tutor.quiz_bank import QUIZ_BANK

pytestmark = pytest.mark.prereqai

TEXT = (Path(__file__).resolve().parents[2] / "ARCHITECTURE.md").read_text(encoding="utf-8")


def test_the_quoted_concept_and_rule_counts_match_the_code():
    concepts, rules = len(ConceptRegistry().all()), len(PrerequisiteDetector.PREREQUISITE_RULES)
    assert f"{concepts} registry concepts" in TEXT and f"{rules} `concept" in TEXT and f"{rules} rules over" in TEXT and f"{rules} hard-coded rules" in TEXT


def test_every_registry_concept_has_a_quiz_as_the_document_says():
    assert set(QUIZ_BANK) == {c.name for c in ConceptRegistry().all()}
