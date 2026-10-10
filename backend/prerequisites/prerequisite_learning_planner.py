from backend.models import (
    Paper,
    LearningStep,
)


class PrerequisiteLearningPlanner:
    """
    Generates a deterministic learning plan
    from the detected missing prerequisites.
    """

    STUDY_ORDER = {

        "Linear Algebra": 1,
        "Probability": 2,
        "Calculus": 3,
        "Graphs": 4,
        "Neural Networks": 5,
        "Sequence Models": 6,
        "Attention": 7,
        "Self-Attention": 8,
        "Multi-Head Attention": 9,
        "Transformer": 10,
    }

    STUDY_TIME = {

        "Linear Algebra": 12,
        "Probability": 10,
        "Calculus": 10,
        "Graphs": 8,
        "Neural Networks": 15,
        "Sequence Models": 12,
        "Attention": 8,
        "Self-Attention": 6,
        "Multi-Head Attention": 6,
        "Transformer": 10,
    }

    def generate(
        self,
        paper: Paper,
    ) -> Paper:

        paper.learning_plan.clear()

        missing = [

            prerequisite

            for prerequisite in paper.missing_prerequisites

            if not prerequisite.satisfied
        ]

        missing.sort(

            key=lambda prerequisite:

            self.STUDY_ORDER.get(
                prerequisite.concept,
                999,
            )
        )

        for index, prerequisite in enumerate(
            missing,
            start=1,
        ):

            paper.learning_plan.append(

                LearningStep(

                    order=index,

                    concept=prerequisite.concept,

                    estimated_hours=self.STUDY_TIME.get(
                        prerequisite.concept,
                        5,
                    ),
                )
            )

        return paper
