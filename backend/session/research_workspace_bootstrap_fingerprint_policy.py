from typing import Mapping

from .research_workspace_bootstrap_projection import (
    ResearchWorkspaceBootstrapProjection,
)


class ResearchWorkspaceBootstrapFingerprintPolicy:
    """
    Fingerprinting policy for bootstrap projections.

    The bootstrap projection exposes:
    - capabilities: Available workspace functionality
    - readiness: Current readiness status and assessments
    - overview: Workspace state summary
    - attention: Items requiring review or action
    - workspace_actions: Available user actions
    - recent_sessions: Recently accessed sessions
    - recent_activity: Recent workspace activity

    Semantic sections for fingerprinting:
    - readiness: Core capability assessment
    - attention: Issues requiring attention
    - actions: Available recommended actions
    - insights: Derived insights (if present)
    - recent_activity: Chronologically ordered recent events

    This policy excludes:
    - capabilities (these are static system metadata)
    - overview (this is mostly metadata)
    - recent_sessions (these are derived from activity)
    """

    @property
    def projection_name(
        self,
    ) -> str:
        return "workspace.bootstrap"

    def extract_sections(
        self,
        projection: object,
    ) -> Mapping[str, object]:
        """
        Extracts semantic sections from a bootstrap projection.

        The projection should be a ResearchWorkspaceBootstrapProjection,
        though we use duck typing to be flexible.
        """

        if not isinstance(
            projection,
            ResearchWorkspaceBootstrapProjection,
        ):
            projection = ResearchWorkspaceBootstrapProjection(
                capabilities=getattr(
                    projection,
                    'capabilities',
                    [],
                ),
                readiness=getattr(
                    projection,
                    'readiness',
                    None,
                ),
                overview=getattr(
                    projection,
                    'overview',
                    None,
                ),
                attention=getattr(
                    projection,
                    'attention',
                    None,
                ),
                workspace_actions=getattr(
                    projection,
                    'workspace_actions',
                    [],
                ),
                recent_sessions=getattr(
                    projection,
                    'recent_sessions',
                    [],
                ),
                recent_activity=getattr(
                    projection,
                    'recent_activity',
                    [],
                ),
            )

        sections = {}

        # Readiness: Core capability assessment
        if hasattr(projection, 'readiness') and (
            projection.readiness is not None
        ):
            sections['readiness'] = (
                projection.readiness
            )

        # Attention: Items requiring attention
        if hasattr(projection, 'attention') and (
            projection.attention is not None
        ):
            sections['attention'] = (
                projection.attention
            )

        # Actions: Available workspace actions
        # Rename from workspace_actions for semantic clarity
        if hasattr(
            projection,
            'workspace_actions',
        ) and projection.workspace_actions:
            sections['actions'] = (
                projection.workspace_actions
            )

        # Recent Activity: Chronologically ordered events
        if hasattr(
            projection,
            'recent_activity',
        ) and projection.recent_activity:
            sections['recent_activity'] = (
                projection.recent_activity
            )

        return sections

    def normalize_section(
        self,
        *,
        section_name: str,
        value: object,
    ) -> object:
        """
        Normalizes a bootstrap section.

        For most sections, returns the value as-is
        since ordering and structure are meaningful.
        """

        # All sections are returned as-is.
        # Ordering is preserved since:
        # - attention items may be prioritized
        # - actions may be ranked by recommendation
        # - recent_activity is chronological

        return value
