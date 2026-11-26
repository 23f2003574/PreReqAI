"""A concept the paper only names while discussing other work does not make its prerequisites the learner's problem, and a subsection of a related-work section is related work too."""
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph, PaperSection
from backend.prerequisites.missing_prerequisite_analyzer import section_role, section_roles
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

pytestmark = pytest.mark.prereqai
METHOD = "We study Transformer language models. We fine-tune the Transformer with gradient descent and a softmax output. Attention layers read the prompt."
RELATED = "Recent work injects numeric reasoning, including a graph neural network (Ran et al., 2019) (Andor et al., 2019)."


def paper_with(*parts):
    paper = Paper(source_path="x", metadata=None)
    paper.sections = [PaperSection(title=title, content=text) for title, text in parts]
    paper.paragraphs = [Paragraph(paragraph_id=n, section_title=title, content=text) for n, (title, text) in enumerate(parts, 1)]
    RuleBasedConceptDetector().detect(paper)
    return paper


def test_a_subsection_of_a_related_work_section_inherits_the_related_role_but_other_subsections_do_not():
    roles = section_roles(["1 Introduction", "2 Method", "2.1 Setup", "C Additional Related Work", "C.4 Numeric and logical reasoning", "C.5 Intermediate language steps", "D Experiments", "D.1 Results"])
    assert roles["C.4 Numeric and logical reasoning"] == roles["C.5 Intermediate language steps"] == roles["C Additional Related Work"] == "related"
    assert roles["2.1 Setup"] != "related" and roles["D.1 Results"] != "related" and roles["1 Introduction"] != "related"
    assert section_role("C.4 Numeric and logical reasoning") == "other"  # the title alone says nothing: the parent does


def test_concepts_named_only_in_related_work_do_not_create_prerequisites():
    paper = paper_with(("2 Method", METHOD), ("C Additional Related Work", "We discuss other work."), ("C.4 Numeric and logical reasoning", RELATED))
    names = {c.name for c in paper.concepts}
    assert "Graph Neural Network" in names and "Transformer" in names  # still detected and shown
    assert PrerequisiteDetector._cited_only(paper) == {"Graph Neural Network"}
    PrerequisiteDetector().detect(paper)
    needed = {p.concept: [e["concept"] for e in p.evidence] for p in paper.prerequisites}
    assert "Graphs" not in needed
    assert all("Graph Neural Network" not in dependents for dependents in needed.values())


def test_a_concept_that_is_also_used_in_the_method_still_drives_its_prerequisites():
    both = paper_with(("2 Method", METHOD + " We also train a graph neural network over the layers."), ("C Additional Related Work", "x"), ("C.5 Intermediate language steps", RELATED))
    assert "Graph Neural Network" not in PrerequisiteDetector._cited_only(both)
    PrerequisiteDetector().detect(both)
    assert any("Graph Neural Network" in [e["concept"] for e in p.evidence] for p in both.prerequisites)


def test_a_paper_without_related_work_sections_is_unchanged():
    plain = paper_with(("2 Method", METHOD + " " + RELATED))
    assert PrerequisiteDetector._cited_only(plain) == set()
    assert PrerequisiteDetector._cited_only(Paper(source_path="x", metadata=None)) == set()
