"""Section roles come from whole words and the neighbouring sections, not from substrings of the title."""
import pytest

from backend.prerequisites.missing_prerequisite_analyzer import section_role, section_roles

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("title,role", [
    ("4 Direct Preference Optimization", "other"),  # "Preference" is not "reference"; the title alone says nothing
    ("Preference Learning Results", "other"),
    ("References", "related"), ("7 References", "related"), ("Bibliography", "related"), ("Reference List", "related"),
    ("Acknowledgements", "related"), ("Acknowledgments", "related"), ("2 Related Work", "related"), ("C Extended Related Work", "related"),
    ("Background and Related Work", "related"),
    ("2 Architectural details", "instructional"), ("3 Preliminaries", "instructional"), ("Methodology", "instructional"), ("5 Theoretical Analysis of DPO", "instructional"),
    ("Algorithm", "instructional"), ("Problem Setup", "instructional"),
    ("6 Experiments", "other"), ("Abstract", "other"), ("Reference models in practice", "other"),
])
def test_title_roles(title, role):
    assert section_role(title) == role


def test_a_method_named_after_the_papers_idea_is_instructional_by_context():
    dpo = ["Abstract", "1 Introduction", "2 Related Work", "3 Preliminaries", "4 Direct Preference Optimization", "5 Theoretical Analysis of DPO", "6 Experiments", "References"]
    roles = section_roles(dpo)
    assert roles["4 Direct Preference Optimization"] == "instructional" and roles["6 Experiments"] == "other" and roles["References"] == "related"
    cot = ["Abstract", "Introduction", "2 Chain-of-Thought Prompting", "3 Arithmetic Reasoning", "4 Commonsense Reasoning", "5 Symbolic Reasoning", "6 Discussion"]
    roles = section_roles(cot)
    assert roles["2 Chain-of-Thought Prompting"] == "instructional"
    assert {roles[t] for t in cot[3:]} == {"other"}  # the experiments that follow the method are not method sections


def test_context_never_promotes_results_or_appendices():
    roles = section_roles(["1 Introduction", "2 Results", "3 Discussion", "A Appendix", "4 Our Idea"])
    assert set(roles.values()) == {"other"}
    assert section_roles(["Intro"])["Intro"] == "other"
