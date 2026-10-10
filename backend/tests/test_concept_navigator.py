from backend.navigation import (
    ConceptNavigator,
)

from backend.models import (
    Paper,
    DetectedConcept,
    ConceptExplanation,
)


def test_concept_navigator_finds_concept_with_explanation():

    navigator = (
        ConceptNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        concepts=[
            DetectedConcept(
                name="Attention",
                domain="transformers",
                occurrences=12,
            )
        ],

        concept_explanations=[
            ConceptExplanation(
                concept="Attention",
                definition="A mechanism that allows a model to focus on the most relevant parts of an input sequence.",
                difficulty="Intermediate",
            )
        ],
    )

    result = navigator.navigate(
        paper,
        "attention",
    )

    assert result.target == "concept"
    assert result.title == "Attention"
    assert "focus on the most relevant" in result.summary
    assert result.metadata["domain"] == "transformers"
    assert result.metadata["occurrences"] == 12


def test_concept_navigator_falls_back_without_explanation():

    navigator = (
        ConceptNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        concepts=[
            DetectedConcept(
                name="Residual Connection",
                domain="transformers",
                occurrences=3,
            )
        ],
    )

    result = navigator.navigate(
        paper,
        "Residual Connection",
    )

    assert result.summary == "No description available for this concept."


def test_concept_navigator_raises_when_not_found():

    navigator = (
        ConceptNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "Nonexistent Concept",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
