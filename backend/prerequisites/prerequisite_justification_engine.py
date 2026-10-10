from backend.models import (
    Paper,
    PrerequisiteJustification,
)


class PrerequisiteJustificationEngine:
    """
    Explains why each prerequisite concept
    is required for understanding the paper.
    """

    JUSTIFICATIONS = {

        "Linear Algebra":
            "Matrix operations and vector representations are fundamental to many modern machine learning models.",

        "Probability":
            "Probability is required to understand prediction confidence, likelihoods, and normalization functions such as Softmax.",

        "Neural Networks":
            "The paper builds upon neural network architectures and assumes familiarity with their components.",

        "Attention":
            "The paper extends or relies upon attention mechanisms as a core modeling technique.",

        "Transformer":
            "Several ideas in the paper build directly upon the Transformer architecture.",
    }

    def justify(
        self,
        paper: Paper,
    ) -> Paper:

        paper.prerequisite_justifications.clear()

        for prerequisite in paper.prerequisites:

            justification = self.JUSTIFICATIONS.get(

                prerequisite.concept,

                "This concept provides foundational knowledge required by later sections of the paper.",
            )

            paper.prerequisite_justifications.append(

                PrerequisiteJustification(

                    concept=prerequisite.concept,

                    justification=justification,
                )
            )

        return paper
