from backend.models import (
    Paper,
    StudyProgress,
)


class StudyProgressTracker:
    """
    Initializes progress tracking for the
    generated study roadmap.
    """

    def initialize(
        self,
        paper: Paper,
    ) -> Paper:

        paper.study_progress.clear()

        for roadmap_step in paper.study_roadmap:

            paper.study_progress.append(

                StudyProgress(

                    concept=roadmap_step.concept,

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
