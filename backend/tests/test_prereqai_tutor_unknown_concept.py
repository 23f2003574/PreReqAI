"""A definition question about a concept outside the built-in registry says so; registered concepts keep their answers."""
from backend.ingestion import DocumentMetadata
from backend.models import DetectedConcept, Paper
from backend.session import LearningSession, RetrievedContext, TutorMode
from backend.tutor import RuleBasedTutor


def _ask(question, concepts=()):
    paper = Paper(source_path="p.pdf", metadata=DocumentMetadata(title='T', author='A', subject='', keywords='', creator='', producer='', page_count=1))
    paper.concepts = [DetectedConcept(name=n, domain="d", occurrences=1) for n in concepts]
    context = RetrievedContext(concepts=list(concepts), sections=[], equations=[])
    return RuleBasedTutor().answer(LearningSession(), paper, context, question, TutorMode.INTUITION)


def test_unknown_concept_is_named_as_unsupported_without_an_invented_definition():
    response = _ask("What is a flux capacitor?")
    assert "'flux capacitor' is not in PreReqAI's built-in concept registry" in response.answer
    assert "tutoring model has not yet been configured" in response.answer  # the no-model warning is kept
    assert response.confidence == 0.0


def test_registered_concept_keeps_its_built_in_answer():
    response = _ask("What is Attention?")
    assert "not in PreReqAI's built-in concept registry" not in response.answer


def test_other_unanswerable_questions_keep_the_plain_placeholder():
    response = _ask("Tell me a joke")
    assert response.answer == "A tutoring model has not yet been configured."
