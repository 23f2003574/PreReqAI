"""A prerequisite is covered only when it is discussed where a paper teaches (Background, Preliminaries, Method...), not by mentions in Related Work."""
import pytest

from backend.models import DetectedConcept, Paper, Paragraph, Prerequisite
from backend.prerequisites.missing_prerequisite_analyzer import COVERAGE_MIN_MENTIONS, MissingPrerequisiteAnalyzer, section_role

pytestmark = pytest.mark.prereqai


def analyse(*sections, subject="Attention", detected=True):
    """`sections`: (title, text) pairs. The mention counts come from the text, as in a real analysis."""
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs = [Paragraph(i, title, text) for i, (title, text) in enumerate(sections, 1)]
    if detected:
        total = sum(text.lower().count("attention") for _, text in sections if not section_role(_) == "related" and "reference" not in _.lower())
        paper.concepts = [DetectedConcept(name=subject, domain="transformers", occurrences=max(total, 1))]
    paper.prerequisites = [Prerequisite(concept=subject, reason="r", confidence=1.0)]
    return MissingPrerequisiteAnalyzer().analyze(paper).missing_prerequisites[0]


THREE = "attention. attention. attention."


@pytest.mark.parametrize("title, role", [
    ("2 Method", "instructional"), ("Methods", "instructional"), ("3.1 Model Architecture", "instructional"), ("Background", "instructional"),
    ("II. PRELIMINARIES", "instructional"), ("Preliminaries and Notation", "instructional"), ("Problem Setup", "instructional"),
    ("Proposed Approach", "instructional"), ("Related Work", "related"), ("2 Related Works", "related"), ("Background and Related Work", "related"),
    ("References", "related"), ("Acknowledgements", "related"), ("Abstract", "other"), ("1 Introduction", "other"), ("Experiments", "other"),
    ("Front Matter", "other"), ("Cited Literature of Interest", "related"), ("Zebra Considerations", "other"), ("", "other"), (None, "other"),
])
def test_section_roles(title, role):
    assert section_role(title) == role


@pytest.mark.parametrize("title", ["Background", "Preliminaries", "2 Method"])
def test_three_mentions_in_a_teaching_section_are_coverage(title):
    item = analyse((title, THREE))
    assert item.satisfied and item.status == "covered" and item.mentions == 3
    assert item.sections == [{"section": title, "mentions": 3, "role": "instructional"}] and title in item.reason


def test_repeated_mentions_inside_one_section_count_together():
    assert analyse(("Method", "attention. " * 7)).sections[0]["mentions"] == 7


def test_mentions_only_in_related_work_are_not_coverage():
    item = analyse(("2 Related Work", "attention. " * 6), ("References", "attention. " * 6))
    assert not item.satisfied and item.status == "mentioned_only" and "only where other work is cited" in item.reason and item.mentions >= 1


def test_related_work_mentions_do_not_help_a_single_method_mention():
    item = analyse(("2 Related Work", "attention. attention."), ("3 Method", "attention."))
    assert not item.satisfied and item.status == "mentioned_only" and "too little" in item.reason


def test_mentions_spread_across_sections_cover_when_one_of_them_teaches():
    item = analyse(("Abstract", "attention."), ("1 Introduction", "attention."), ("3 Method", "attention."))
    assert item.satisfied and [s["role"] for s in item.sections] == ["other", "other", "instructional"]


def test_enough_mentions_but_none_where_it_is_taught_is_not_coverage():
    item = analyse(("Abstract", "attention."), ("1 Introduction", "attention. attention."), ("Experiments", "attention."))
    assert not item.satisfied and item.status == "mentioned_only" and "none in a Background, Preliminaries or Method section" in item.reason


def test_an_unrecognised_section_title_never_claims_coverage():
    item = analyse(("Zebra Considerations", THREE))
    assert not item.satisfied and item.sections[0]["role"] == "other"


def test_missing_section_information_never_claims_coverage():
    paper = Paper(source_path="p.pdf", metadata=None)  # no paragraphs at all: counts exist, but where the mentions are is unknown
    paper.concepts = [DetectedConcept(name="Attention", domain="transformers", occurrences=5)]
    paper.prerequisites = [Prerequisite(concept="Attention", reason="r", confidence=1.0)]
    item = MissingPrerequisiteAnalyzer().analyze(paper).missing_prerequisites[0]
    assert (item.status, item.mentions, item.satisfied, item.sections) == ("mentioned_only", 5, False, [])


def test_a_subject_that_is_not_a_registry_concept_follows_the_same_policy():
    taught = analyse(("Preliminaries", "A random variable, a joint probability distribution and a random variable again."), subject="Probability", detected=False)
    cited = analyse(("Related Work", "A random variable, a joint probability distribution and a random variable again."), subject="Probability", detected=False)
    assert taught.satisfied and taught.mentions == 3 and not cited.satisfied and cited.mentions == 3


def test_the_threshold_is_unchanged_and_the_section_evidence_reaches_the_report():
    assert COVERAGE_MIN_MENTIONS == 3
    from backend.platform import platform

    report = platform.analyze("examples/prerequisites/sample-paper.pdf")["report"]
    attention = next(m for m in report["missing_prerequisites"] if m["concept"] == "Attention")
    assert attention["status"] == "covered" and attention["mentions"] == 4
    assert {s["section"] for s in attention["sections"]} >= {"2 Method"} and all({"section", "mentions", "role"} <= set(s) for s in attention["sections"])
