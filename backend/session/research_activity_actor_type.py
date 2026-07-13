from enum import (
    Enum,
)


class ResearchActivityActorType(
    str,
    Enum,
):
    """
    Identifies the category of actor
    responsible for a research activity.
    """

    USER = "user"

    SYSTEM = "system"

    AI = "ai"

    AUTOMATION = "automation"

    API = "api"
