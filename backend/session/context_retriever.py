from dataclasses import dataclass

from backend.concepts.rule_based_concept_detector import _BACK_MATTER
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

            # the detector ignores the bibliography and acknowledgements; a cited title is not where the paper covers a concept
            if _BACK_MATTER.match((section.title or "").strip()):
                continue

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
