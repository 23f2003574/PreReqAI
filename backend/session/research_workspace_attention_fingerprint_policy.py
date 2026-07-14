from typing import Mapping

from .research_workspace_attention_projection import (
    ResearchWorkspaceAttentionProjection,
)


class ResearchWorkspaceAttentionFingerprintPolicy:
    """
    Fingerprinting policy for attention projections.

    The attention projection exposes:
    - items: Priority-ordered attention items
    - total_count: Total number of items
    - actionable_count: Items requiring action
    - critical_count: Critical priority items
    - high_count: High priority items

    Semantic sections for fingerprinting:
    - items: The actual attention items (core semantic content)

    This policy excludes:
    - Count fields (these are derived from items)

    The items are preserved in their original
    priority order since that ordering is meaningful
    to the consumer.
    """

    @property
    def projection_name(
        self,
    ) -> str:
        return "workspace.attention"

    def extract_sections(
        self,
        projection: object,
    ) -> Mapping[str, object]:
        """
        Extracts semantic sections from an attention projection.
        """

        if not isinstance(
            projection,
            ResearchWorkspaceAttentionProjection,
        ):
            projection = ResearchWorkspaceAttentionProjection(
                items=getattr(
                    projection,
                    'items',
                    [],
                ),
            )

        sections = {}

        # Items: The core semantic content
        if hasattr(projection, 'items'):
            sections['items'] = projection.items

        return sections

    def normalize_section(
        self,
        *,
        section_name: str,
        value: object,
    ) -> object:
        """
        Normalizes an attention section.

        Items are returned as-is since priority
        ordering is consumer-meaningful.
        """

        return value
