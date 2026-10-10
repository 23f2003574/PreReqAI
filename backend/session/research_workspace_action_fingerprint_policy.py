from typing import Mapping

from .research_workspace_action_projection import (
    ResearchWorkspaceActionProjection,
)


class ResearchWorkspaceActionFingerprintPolicy:
    """
    Fingerprinting policy for action projections.

    The action projection exposes:
    - scope: The context scope (workspace, session, etc.)
    - entity_id: Optional entity identifier
    - actions: The available actions
    - available_count: Count of available actions
    - unavailable_count: Count of unavailable actions

    Semantic sections for fingerprinting:
    - actions: The ranked action availability list

    This policy preserves action ordering since
    ranking by recommendation is consumer-meaningful.

    Excludes:
    - Count fields (derived from actions)
    - scope and entity_id (metadata about context)
    """

    @property
    def projection_name(
        self,
    ) -> str:
        return "workspace.actions"

    def extract_sections(
        self,
        projection: object,
    ) -> Mapping[str, object]:
        """
        Extracts semantic sections from an action projection.
        """

        if not isinstance(
            projection,
            ResearchWorkspaceActionProjection,
        ):
            projection = ResearchWorkspaceActionProjection(
                scope=getattr(
                    projection,
                    'scope',
                    None,
                ),
                entity_id=getattr(
                    projection,
                    'entity_id',
                    None,
                ),
                actions=getattr(
                    projection,
                    'actions',
                    [],
                ),
            )

        sections = {}

        # Actions: The core semantic content
        if hasattr(projection, 'actions'):
            sections['actions'] = projection.actions

        return sections

    def normalize_section(
        self,
        *,
        section_name: str,
        value: object,
    ) -> object:
        """
        Normalizes an action section.

        Actions are returned as-is since the
        ranking order is consumer-meaningful.
        """

        return value
