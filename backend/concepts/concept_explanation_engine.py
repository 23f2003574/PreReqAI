from backend.models import (
    Paper,
    ConceptExplanation,
)


class ConceptExplanationEngine:
    """
    Generates deterministic explanations for
    concepts currently supported by PreReqAI.
    """

    EXPLANATIONS = {

        "Transformer": (
            "A neural network architecture that processes sequences using attention mechanisms instead of recurrence.",
            "Intermediate",
        ),

        "Attention": (
            "A mechanism that allows a model to focus on the most relevant parts of an input sequence.",
            "Intermediate",
        ),

        "Multi-Head Attention": (
            "Multiple attention operations performed in parallel to capture different relationships within the input.",
            "Advanced",
        ),

        "Softmax": (
            "A mathematical function that converts scores into probabilities.",
            "Beginner",
        ),

        "Graph Neural Network": (
            "A neural network designed to learn from graph-structured data.",
            "Intermediate",
        ),
    }

    def explain(
        self,
        paper: Paper,
    ) -> Paper:

        paper.concept_explanations.clear()

        for concept in paper.concepts:

            if concept.name not in self.EXPLANATIONS:

                continue

            definition, difficulty = (
                self.EXPLANATIONS[
                    concept.name
                ]
            )

            paper.concept_explanations.append(

                ConceptExplanation(

                    concept=concept.name,

                    definition=definition,

                    difficulty=difficulty,
                )
            )

        return paper
