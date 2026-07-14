from typing import Mapping

from .research_workspace_readiness_assessment import (
    ResearchWorkspaceReadinessAssessment,
)


class ResearchWorkspaceReadinessFingerprintPolicy:
    """
    Fingerprinting policy for readiness assessments.

    The readiness assessment exposes:
    - status: The readiness status (ready, blocked, degraded)
    - ready: Boolean ready flag
    - blocking: Boolean blocking flag
    - checks: Individual readiness checks
    - warnings: Non-blocking warnings
    - blocking_reasons: Reasons for blocking status

    Semantic sections for fingerprinting:
    - status: The current operational status
    - ready: The ready state
    - blocking: The blocking state
    - warnings: Non-blocking warnings
    - blocking_reasons: Reasons blocking operation

    The checks are internal implementation details
    and are excluded from the semantic fingerprint.
    The semantic view focuses on the assessment outcome
    and consumer-visible status.
    """

    @property
    def projection_name(
        self,
    ) -> str:
        return "workspace.readiness"

    def extract_sections(
        self,
        projection: object,
    ) -> Mapping[str, object]:
        """
        Extracts semantic sections from a readiness assessment.
        """

        if not isinstance(
            projection,
            ResearchWorkspaceReadinessAssessment,
        ):
            projection = ResearchWorkspaceReadinessAssessment(
                status=getattr(
                    projection,
                    'status',
                    None,
                ),
                ready=getattr(
                    projection,
                    'ready',
                    False,
                ),
                blocking=getattr(
                    projection,
                    'blocking',
                    False,
                ),
                warnings=getattr(
                    projection,
                    'warnings',
                    [],
                ),
                blocking_reasons=getattr(
                    projection,
                    'blocking_reasons',
                    [],
                ),
            )

        sections = {}

        # Status: The operational assessment
        if hasattr(projection, 'status'):
            sections['status'] = projection.status

        # Ready: Ready flag
        if hasattr(projection, 'ready'):
            sections['ready'] = projection.ready

        # Blocking: Blocking flag
        if hasattr(projection, 'blocking'):
            sections['blocking'] = (
                projection.blocking
            )

        # Warnings: Non-blocking warnings
        if hasattr(projection, 'warnings') and (
            projection.warnings
        ):
            sections['warnings'] = (
                projection.warnings
            )

        # Blocking Reasons: Why operation is blocked
        if hasattr(
            projection,
            'blocking_reasons',
        ) and projection.blocking_reasons:
            sections['blocking_reasons'] = (
                projection.blocking_reasons
            )

        return sections

    def normalize_section(
        self,
        *,
        section_name: str,
        value: object,
    ) -> object:
        """
        Normalizes a readiness section.

        All sections are returned as-is.
        """

        return value
