from backend.prerequisites.difficulty_assessment_engine import describe_contributors, prerequisite_effort
from backend.models import (
    Paper,
    DifficultyExplanation,
)


class DifficultyExplanationEngine:
    """
    Explains why a research paper received
    its difficulty assessment.
    """

    def explain(
        self,
        paper: Paper,
    ) -> Paper:

        paper.difficulty_explanations.clear()

        effort = prerequisite_effort(paper)
        missing = len(effort)

        if not paper.concepts and not paper.missing_prerequisites:

            paper.difficulty_explanations.append(

                DifficultyExplanation(

                    title="Insufficient Evidence",

                    description="No known concepts were detected, so the difficulty could not be assessed.",
                )
            )

        if missing:

            paper.difficulty_explanations.append(

                DifficultyExplanation(

                    title="Missing Prerequisites",

                    description=(
                        f"{missing} prerequisite concepts require external study, about {sum(entry[1] for entry in effort):g} hours: "
                        f"{describe_contributors(effort)}."
                    ),
                )
            )

        if len(paper.equations):

            paper.difficulty_explanations.append(

                DifficultyExplanation(

                    title="Mathematical Content",

                    description=(
                        f"The paper contains "
                        f"{len(paper.equations)} equations."
                    ),
                )
            )

        if len(paper.algorithms):

            paper.difficulty_explanations.append(

                DifficultyExplanation(

                    title="Algorithmic Complexity",

                    description=(
                        f"The paper introduces "
                        f"{len(paper.algorithms)} algorithms."
                    ),
                )
            )

        if len(paper.concepts):

            paper.difficulty_explanations.append(

                DifficultyExplanation(

                    title="Concept Density",

                    description=(
                        f"The paper discusses "
                        f"{len(paper.concepts)} detected concepts."
                    ),
                )
            )

        return paper
