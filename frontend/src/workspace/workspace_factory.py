from .visual_research_workspace import (
    VisualResearchWorkspace,
)


def create_visual_research_workspace(

    correlation_provider=None,

):
    """
    Creates a fully configured visual
    research workspace.
    """

    return VisualResearchWorkspace(

        correlation_provider=(
            correlation_provider
        )
    )
