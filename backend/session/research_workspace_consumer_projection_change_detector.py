from typing import Mapping

from .research_workspace_consumer_projection_change_report import (
    ResearchWorkspaceConsumerProjectionChangeReport,
)

from .research_workspace_consumer_projection_change_status import (
    ResearchWorkspaceConsumerProjectionChangeStatus,
)

from .research_workspace_consumer_projection_fingerprint_snapshot import (
    ResearchWorkspaceConsumerProjectionFingerprintSnapshot,
)

from .research_workspace_consumer_projection_section_change import (
    ResearchWorkspaceConsumerProjectionSectionChange,
)

from .research_workspace_consumer_projection_section_change_status import (
    ResearchWorkspaceConsumerProjectionSectionChangeStatus,
)


class ResearchWorkspaceConsumerProjectionChangeDetector:
    """
    Service for detecting semantic changes between
    two consumer projection fingerprint snapshots.

    Compares snapshots to determine:
    - Is the overall state unchanged, changed, or incomparable?
    - Which specific sections changed?
    - Were sections added or removed?

    This service works entirely from fingerprint snapshots,
    not from the original projections. This is important:
    - Comparison is very fast and cheap
    - Comparison requires no raw projection objects
    - Enables future integration with caching, ETags, etc.

    Snapshots are incomparable if:
    - Projection names differ
    - Contract versions differ (or configured as incompatible)
    """

    def compare(
        self,
        *,
        previous: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ),
        current: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ),
    ) -> ResearchWorkspaceConsumerProjectionChangeReport:
        """
        Compares two fingerprint snapshots and produces
        a change report.

        Arguments:
            previous: The previous fingerprint snapshot
            current: The current fingerprint snapshot

        Returns:
            An immutable change report describing detected changes
        """

        # Check if snapshots are comparable
        if previous.projection_name != current.projection_name:
            return self._incomparable_report(
                previous=previous,
                current=current,
                reason="projection_name_mismatch",
            )

        # For now, use conservative version comparison:
        # Different versions are incomparable unless
        # explicit compatibility logic exists (from Commit #7)
        if previous.contract_version != current.contract_version:
            if previous.contract_version is not None or (
                current.contract_version is not None
            ):
                return self._incomparable_report(
                    previous=previous,
                    current=current,
                    reason="contract_version_mismatch",
                )

        # Comparable: perform detailed comparison

        # Fast path: if overall fingerprints match, nothing changed
        if previous.overall == current.overall:
            return ResearchWorkspaceConsumerProjectionChangeReport(
                projection_name=previous.projection_name,
                status=(
                    ResearchWorkspaceConsumerProjectionChangeStatus.UNCHANGED
                ),
                previous=previous,
                current=current,
                section_changes=(),
            )

        # Overall fingerprints differ: compare sections
        section_changes = self._compare_sections(
            previous=previous,
            current=current,
        )

        # Determine if any section changed
        changed_any = any(
            change.status != (
                ResearchWorkspaceConsumerProjectionSectionChangeStatus.UNCHANGED
            )
            for change in section_changes
        )

        status = (
            ResearchWorkspaceConsumerProjectionChangeStatus.CHANGED
            if changed_any
            else ResearchWorkspaceConsumerProjectionChangeStatus.UNCHANGED
        )

        return ResearchWorkspaceConsumerProjectionChangeReport(
            projection_name=previous.projection_name,
            status=status,
            previous=previous,
            current=current,
            section_changes=tuple(section_changes),
        )

    def _compare_sections(
        self,
        *,
        previous: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ),
        current: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ),
    ) -> list[ResearchWorkspaceConsumerProjectionSectionChange]:
        """
        Compares sections between previous and current snapshots.

        Returns a list of section changes, sorted by section name.
        """

        # Build maps for easy lookup
        previous_sections: Mapping[
            str,
            ResearchWorkspaceConsumerProjectionSectionChangeStatus,
        ] = {
            sf.section_name: sf.fingerprint
            for sf in previous.sections
        }

        current_sections: Mapping[
            str,
            ResearchWorkspaceConsumerProjectionSectionChangeStatus,
        ] = {
            sf.section_name: sf.fingerprint
            for sf in current.sections
        }

        all_section_names = sorted(
            set(previous_sections.keys())
            | set(current_sections.keys())
        )

        changes = []

        for section_name in all_section_names:
            previous_fp = previous_sections.get(
                section_name,
            )

            current_fp = current_sections.get(
                section_name,
            )

            # Determine change status
            if previous_fp is None:
                # Section added
                status = (
                    ResearchWorkspaceConsumerProjectionSectionChangeStatus.ADDED
                )

            elif current_fp is None:
                # Section removed
                status = (
                    ResearchWorkspaceConsumerProjectionSectionChangeStatus.REMOVED
                )

            elif previous_fp == current_fp:
                # Section unchanged
                status = (
                    ResearchWorkspaceConsumerProjectionSectionChangeStatus.UNCHANGED
                )

            else:
                # Section changed
                status = (
                    ResearchWorkspaceConsumerProjectionSectionChangeStatus.CHANGED
                )

            change = (
                ResearchWorkspaceConsumerProjectionSectionChange(
                    section_name=section_name,
                    status=status,
                    previous_fingerprint=previous_fp,
                    current_fingerprint=current_fp,
                )
            )

            changes.append(change)

        return changes

    def _incomparable_report(
        self,
        *,
        previous: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ),
        current: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ),
        reason: str,
    ) -> ResearchWorkspaceConsumerProjectionChangeReport:
        """
        Creates a change report for incomparable snapshots.
        """

        return ResearchWorkspaceConsumerProjectionChangeReport(
            projection_name=(
                f"{previous.projection_name}/"
                f"{current.projection_name}"
            ),
            status=(
                ResearchWorkspaceConsumerProjectionChangeStatus.INCOMPARABLE
            ),
            previous=previous,
            current=current,
            section_changes=(),
        )
