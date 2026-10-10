from backend.models import (
    Paper,
    StudyProgress,
)


class StudyProgressTracker:
    """
    Initializes progress tracking for the
    learning plan: every planned concept, including those with no curated resource.
    """

    def initialize(
        self,
        paper: Paper,
    ) -> Paper:

        paper.study_progress.clear()

        for plan_step in paper.learning_plan:

            paper.study_progress.append(

                StudyProgress(

                    concept=plan_step.concept,

                    completed=False,

                    progress_percent=0,
                )
            )

        return paper

    def complete(
        self,
        paper: Paper,
        concept: str,
    ) -> Paper:

        for progress in paper.study_progress:

            if progress.concept == concept:

                progress.completed = True

                progress.progress_percent = 100

        return paper
