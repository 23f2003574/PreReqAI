from backend.engine import (
    InteractiveResearchEngine,
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


# The one platform instance the HTTP application (backend.main) and its routers
# share, so the user-facing endpoints run the platform's own pipelines.
platform = PreReqAIPlatform()
