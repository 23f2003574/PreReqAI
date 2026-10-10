from dataclasses import dataclass

from backend.models import (
    Paper,
)


@dataclass
class RetrievedContext:

    concepts: list[str]

    sections: list[str]

    equations: list[str]


class ContextRetriever:
    """
    Retrieves paper context relevant to a learner's question.
    """

    def retrieve(
        self,
        paper: Paper,
        question: str,
    ) -> RetrievedContext:

        concepts = []
        sections = []
        equations = []

        query = question.lower()

        for concept in paper.concepts:

            if concept.name.lower() in query:

                concepts.append(
                    concept.name,
                )

        for section in paper.sections:

            if any(
                concept.lower() in section.content.lower()
                for concept in concepts
            ):
                sections.append(
                    section.title,
                )

        for equation in paper.equations:

            if equation.section in sections:

                equations.append(
                    equation.expression,
                )

        return RetrievedContext(
            concepts=concepts,
            sections=sections,
            equations=equations,
        )
