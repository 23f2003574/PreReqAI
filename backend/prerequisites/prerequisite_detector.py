from backend.models import (
    Paper,
    Prerequisite,
)


class PrerequisiteDetector:
    """
    Identifies prerequisite concepts required
    to understand a research paper.

    The initial implementation uses deterministic
    rules derived from the detected concepts.
    """

    PREREQUISITE_RULES = {

        "Transformer": [
            "Attention",
            "Neural Networks",
        ],

        "Multi-Head Attention": [
            "Attention",
            "Linear Algebra",
        ],

        "Attention": [
            "Linear Algebra",
            "Probability",
        ],

        "Softmax": [
            "Probability",
        ],

        "Graph Neural Network": [
            "Graphs",
            "Neural Networks",
        ],

        "Policy Gradient": [
            "Markov Decision Process",
            "Probability",
        ],
    }

    def detect(
        self,
        paper: Paper,
    ) -> Paper:

        paper.prerequisites.clear()

        discovered = set()

        for concept in paper.concepts:

            for prerequisite in self.PREREQUISITE_RULES.get(
                concept.name,
                [],
            ):

                if prerequisite in discovered:
                    continue

                paper.prerequisites.append(

                    Prerequisite(

                        concept=prerequisite,

                        reason=(
                            f"Required to understand "
                            f"{concept.name}"
                        ),

                        confidence=1.0,
                    )
                )

                discovered.add(prerequisite)

        return paper
