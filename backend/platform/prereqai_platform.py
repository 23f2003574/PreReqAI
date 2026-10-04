from backend.engine import (
    InteractiveResearchEngine,
)

from backend.api.workflow_result import (
    failure_body,
    success_body,
)

from backend.pipeline import (
    InteractiveLearningPipeline,
    ResearchNavigationPipeline,
    ResearchPaperPipeline,
)


class PreReqAIPlatform:
    """
    High-level platform entry point
    coordinating every educational
    subsystem: analysis (PDF to
    knowledge graph and prerequisites),
    navigation, interaction, and the
    learning workflow/tutoring pipeline.
    """

    def __init__(self):

        self.analysis = (
            ResearchPaperPipeline()
        )

        self.navigation = (
            ResearchNavigationPipeline()
        )

        self.interaction = (
            InteractiveResearchEngine()
        )

        self.learning = (
            InteractiveLearningPipeline()
        )

    def analyze(self, file_path: str) -> dict:
        """Run the analysis pipeline on a paper PDF and open a learning
        session for it. Returns the public workflow result envelope
        (backend.api.workflow_result): a success body carrying session_id and
        report, or a failure body for the analysis stage. This is the one
        place the analysis workflow is turned into a public result; the HTTP
        endpoint and the CLI both call it."""
        from backend.session import session_manager

        try:
            result = self.analysis.run(file_path)
        except Exception as exc:
            return failure_body(
                "analysis", f"Failed to process the uploaded paper: {exc}", error=exc,
                hint="Upload a text-based PDF research paper.",
            )
        session = session_manager.create(
            paper_title=result.report["paper"]["title"], report=result.report, paper=result.paper,
        )
        return success_body(
            "Prerequisite Explorer", "session_created", session_id=session.session_id, report=result.report,
        )


# The one platform instance the HTTP application (backend.main) and its routers
# share, so the user-facing endpoints run the platform's own pipelines.
platform = PreReqAIPlatform()
