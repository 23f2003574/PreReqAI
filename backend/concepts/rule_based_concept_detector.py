import re

from backend.models import (
    Paper,
    DetectedConcept,
)

from .concept_registry import ConceptRegistry


class RuleBasedConceptDetector:
    """
    Detects known concepts using exact,
    case-insensitive matching against the
    Concept Registry, counting a concept's
    whole-word aliases (GNN, DDPM, MDP...) too.
    """

    def __init__(self):

        self.registry = ConceptRegistry()

    def detect(
        self,
        paper: Paper,
    ) -> Paper:

        paper.concepts.clear()

        full_text = "\n".join(
            paragraph.content
            for paragraph in paper.paragraphs
        ).lower()

        # PDF text is hard-wrapped: "policy\ngradient" and "multi-\nhead" must still match their concept
        full_text = re.sub(r"\s+", " ", re.sub(r"-\s*\n\s*", "-", full_text))

        for concept in self.registry.all():

            occurrences = full_text.count(
                concept.name.lower()
            ) + sum(
                len(re.findall(rf"\b{re.escape(alias.lower())}\b", full_text))
                for alias in concept.aliases
            )

            if occurrences == 0:
                continue

            paper.concepts.append(
                DetectedConcept(
                    name=concept.name,
                    domain=concept.domain,
                    occurrences=occurrences,
                )
            )

        return paper
