from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)


class ResearchCheckpointPolicy:
    """
    Determines which research events
    should trigger automatic session
    persistence.
    """

    def __init__(

        self,

        enabled_reasons=None,

    ):

        self.enabled_reasons = set(

            enabled_reasons

            if enabled_reasons is not None

            else {

                ResearchCheckpointReason
                .ARTIFACT_CREATED,

                ResearchCheckpointReason
                .LEARNING_ACTION_COMPLETED,

                ResearchCheckpointReason
                .WORKFLOW_PROGRESS,

                ResearchCheckpointReason
                .RESEARCH_OBJECT_CHANGED,

                ResearchCheckpointReason
                .SECTION_CHANGED,

                ResearchCheckpointReason
                .GRAPH_CONTEXT_CHANGED,

                ResearchCheckpointReason
                .APPLICATION_BACKGROUND,
            }
        )

    def should_checkpoint(

        self,

        reason:
            ResearchCheckpointReason,

    ) -> bool:

        if (

            reason

            == (
                ResearchCheckpointReason
                .MANUAL
            )
        ):

            return True

        return (

            reason

            in self.enabled_reasons
        )
