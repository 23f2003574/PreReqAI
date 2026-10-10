from .artifact_restoration_result import (
    ArtifactRestorationResult,
)


class ResearchArtifactRestorer:
    """
    Restores durable research artifacts
    into contextual learning content
    without re-executing educational
    workflows.
    """

    def __init__(

        self,

        artifact_store,

    ):

        self.artifact_store = (
            artifact_store
        )

    def restore_for_interaction(

        self,

        interaction_id: str,

        artifact_ids: list[str],

        workspace,

    ):

        artifacts = []

        missing = []

        learning_content = []

        for artifact_id in artifact_ids:

            artifact = (

                self.artifact_store.get(

                    artifact_id
                )
            )

            if artifact is None:

                missing.append(
                    artifact_id
                )

                continue

            artifacts.append(
                artifact
            )

            content = (

                self._restore_artifact(

                    artifact,

                    workspace,
                )
            )

            learning_content.append(
                content
            )

        return ArtifactRestorationResult(

            restored=bool(
                learning_content
            ),

            interaction_id=(
                interaction_id
            ),

            artifacts=artifacts,

            learning_content=(
                learning_content
            ),

            missing_artifact_ids=(
                missing
            ),
        )

    def _restore_artifact(

        self,

        artifact,

        workspace,

    ):

        return (

            workspace
            .restore_learning_artifact(

                artifact
            )
        )
