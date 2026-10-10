from backend.models import (
    Paper,
    StudyAction,
)


class StudyActionPlanGenerator:
    """
    Generates concrete study actions from
    prerequisite analysis.
    """

    def generate(
        self,
        paper: Paper,
    ) -> Paper:

        paper.study_actions.clear()

        priority = 1

        for step in paper.learning_plan:

            paper.study_actions.append(

                StudyAction(

                    priority=priority,

                    title=f"Study {step.concept}",

                    description=(
                        f"Spend approximately "
                        f"{step.estimated_hours} hours "
                        f"learning {step.concept} "
                        "before reading this paper."
                    ),
                )
            )

            priority += 1

        return paper
