from dataclasses import dataclass

from pathlib import Path


@dataclass
class ResearchPersistenceConfig:
    """
    Defines filesystem locations for
    persistent research state.
    """

    root_directory: Path

    @property
    def sessions_path(self):

        return (

            self.root_directory

            / "sessions.json"
        )

    @property
    def artifacts_path(self):

        return (

            self.root_directory

            / "artifacts.json"
        )

    @property
    def interaction_links_path(self):

        return (

            self.root_directory

            / "interaction_artifact_links.json"
        )

    @property
    def checkpoints_path(self):

        return (

            self.root_directory

            / "checkpoints.json"
        )

    @property
    def session_versions_path(self):

        return (

            self.root_directory

            / "session_versions.json"
        )

    @property
    def checkpoint_annotations_path(self):

        return (

            self.root_directory

            / "checkpoint_annotations.json"
        )

    @property
    def session_branches_path(self):

        return (

            self.root_directory

            / "session_branches.json"
        )

    @property
    def session_profiles_path(self):

        return (

            self.root_directory

            / "session_profiles.json"
        )

    @property
    def research_tags_path(self):

        return (

            self.root_directory

            / "research_tags.json"
        )

    @property
    def research_collections_path(self):

        return (

            self.root_directory

            / "research_collections.json"
        )

    @property
    def research_activity_events_path(self):

        return (

            self.root_directory

            / "research_activity_events.json"
        )

    @property
    def research_workspace_changes_path(self):

        return (

            self.root_directory

            / "research_workspace_changes.json"
        )
