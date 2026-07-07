from backend.session import (
    ContextRetriever,
)
from backend.models import (
    Paper,
    DetectedConcept,
    PaperSection,
    Equation,
)


def test_context_retrieval():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.concepts.append(
        DetectedConcept(
            name="Attention",
            domain="transformers",
            occurrences=3,
        )
    )

    context = (
        ContextRetriever()
        .retrieve(
            paper,
            "Explain Attention",
        )
    )

    assert (
        "Attention" in context.concepts
    )


def test_context_retrieval_filters_sections_and_equations():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.concepts.append(
        DetectedConcept(
            name="Attention",
            domain="transformers",
        )
    )

    paper.sections.append(
        PaperSection(
            title="3. Attention Mechanism",
            content="This section covers Attention in depth.",
        )
    )

    paper.sections.append(
        PaperSection(
            title="1. Introduction",
            content="This section has nothing relevant.",
        )
    )

    paper.equations.append(
        Equation(
            equation_id=1,
            expression="softmax(QK^T/sqrt(d))",
            section="3. Attention Mechanism",
        )
    )

    paper.equations.append(
        Equation(
            equation_id=2,
            expression="unrelated equation",
            section="1. Introduction",
        )
    )

    context = (
        ContextRetriever()
        .retrieve(
            paper,
            "Explain Attention",
        )
    )

    assert context.sections == [
        "3. Attention Mechanism",
    ]

    assert context.equations == [
        "softmax(QK^T/sqrt(d))",
    ]
