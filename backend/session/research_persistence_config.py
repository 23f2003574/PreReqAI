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
