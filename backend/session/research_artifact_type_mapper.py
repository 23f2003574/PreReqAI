from .research_artifact_type import (
    ResearchArtifactType,
)


class ResearchArtifactTypeMapper:
    """
    Maps educational action names
    to durable artifact categories.
    """

    _MAPPING = {

        "explain":
            ResearchArtifactType
            .EXPLANATION,

        "visualize":
            ResearchArtifactType
            .VISUALIZATION,

        "implement":
            ResearchArtifactType
            .IMPLEMENTATION,

        "compare":
            ResearchArtifactType
            .COMPARISON,

        "quiz":
            ResearchArtifactType
            .QUIZ,

        "summarize":
            ResearchArtifactType
            .SUMMARY,

        "derive":
            ResearchArtifactType
            .DERIVATION,

        "explore":
            ResearchArtifactType
            .EXPLORATION,
    }

    @classmethod
    def from_action(

        cls,

        action,

    ):

        value = (

            action.value

            if hasattr(
                action,
                "value",
            )

            else str(action)
        )

        return cls._MAPPING.get(

            value,

            ResearchArtifactType.OTHER,
        )
