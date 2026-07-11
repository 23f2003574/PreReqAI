from frontend.src.workspace import (
    create_visual_research_workspace,
)


class PreReqAIApplication:
    """
    Application-level entry point
    for the visual PreReqAI experience.
    """

    def __init__(self):

        self.workspace = (
            create_visual_research_workspace()
        )
