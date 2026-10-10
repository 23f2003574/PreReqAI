from ..context_provenance import LLMContextProvenanceService, UnknownProvenanceError
from ..context_snapshot import LLMContextSnapshotService
from ..context_version import UnknownContextVersionError
from ..project_context import LLMProjectContextService, UnknownProjectContextError
from .models import FRESH, STALE, UNKNOWN, LLMContextFreshness


class LLMContextFreshnessService:
    """Detects whether stored context is still current relative to its source.

    Reuses Commit #6's provenance record as the sole source of what to
    compare against, so no second change-tracking system is invented here:

        source_type="context_version"  -> compared against Commit #2's
                                           LLMContextVersionService.latest(),
                                           reached via provenance_service's
                                           own version_service
        source_type="research_artifact" -> compared against the
                                           backend.session artifact store
                                           reached via provenance_service's
                                           own artifact_store
        source_type="project_context"   -> compared against Commit #1's
                                           current updated_at for the
                                           referenced context
        source_type="external", or no provenance at all, or a comparison
        the repository has no collaborator wired to make -> UNKNOWN, never
        silently reported as fresh.

    Every method here only reads through Commits #1/#2/#6/#8; nothing is
    ever written, versioned, or mutated -- detection is read-only, and
    refresh_candidates() only reports what a refresh would use, it never
    applies one.
    """

    def __init__(
        self,
        context_service: LLMProjectContextService,
        provenance_service: LLMContextProvenanceService,
        snapshot_service: LLMContextSnapshotService,
    ):
        self.context_service = context_service
        self.provenance_service = provenance_service
        self.snapshot_service = snapshot_service

    def check(self, context_id: str) -> LLMContextFreshness:
        """Freshness of one stored context, relative to its recorded provenance."""
        self.context_service.get(context_id)

        try:
            provenance = self.provenance_service.get(context_id)
        except UnknownProvenanceError:
            return LLMContextFreshness(
                context_id, UNKNOWN, "no provenance recorded for this context"
            )

        return self._compare(context_id, provenance)

    def check_snapshot(self, snapshot_id: str) -> LLMContextFreshness:
        """Freshness of a Commit #8 snapshot: stale if any item it captured is stale."""
        snapshot = self.snapshot_service.get(snapshot_id)

        results = [self._check_item(item) for item in snapshot.context_items]

        if not results:
            return LLMContextFreshness(
                snapshot.snapshot_id, FRESH, "snapshot carries no context items"
            )

        stale_count = sum(1 for result in results if result.status == STALE)
        unknown_count = sum(1 for result in results if result.status == UNKNOWN)
        fresh_count = len(results) - stale_count - unknown_count

        if stale_count:
            status = STALE
        elif unknown_count:
            status = UNKNOWN
        else:
            status = FRESH

        return LLMContextFreshness(
            snapshot.snapshot_id,
            status,
            f"{stale_count} stale, {unknown_count} unknown, {fresh_count} fresh "
            f"out of {len(results)} context item(s)",
        )

    def stale(self, context_id: str) -> bool:
        """True unless check() finds the context FRESH -- UNKNOWN counts as stale."""
        return self.check(context_id).status != FRESH

    def refresh_candidates(self, context_id: str) -> list:
        """What a refresh of context_id would pull from, without applying it.

        Empty for anything that is not STALE: a FRESH context needs no
        refresh, and an UNKNOWN one has nothing verified to refresh from.
        """
        result = self.check(context_id)
        if result.status != STALE:
            return []

        provenance = self.provenance_service.get(context_id)

        if provenance.source_type == "context_version":
            latest = self.provenance_service.version_service.latest(provenance.source_id)
            return [
                {
                    "source_type": "context_version",
                    "source_id": provenance.source_id,
                    "current_version": latest.version,
                    "current_content": latest.content,
                }
            ]

        if provenance.source_type == "research_artifact":
            artifact = self.provenance_service.artifact_store.get(provenance.source_id)
            return [
                {
                    "source_type": "research_artifact",
                    "source_id": provenance.source_id,
                    "current_version": artifact.version,
                    "current_content": artifact.content,
                }
            ]

        if provenance.source_type == "project_context":
            source = self.context_service.get(provenance.source_id)
            return [
                {
                    "source_type": "project_context",
                    "source_id": provenance.source_id,
                    "current_version": None,
                    "current_content": source.content,
                }
            ]

        return []

    # -- internals ----------------------------------------------------------

    def _check_item(self, item: dict) -> LLMContextFreshness:
        context_id = item.get("context_id")
        if not context_id:
            return LLMContextFreshness(None, UNKNOWN, "context item carries no context_id")
        try:
            return self.check(context_id)
        except UnknownProjectContextError:
            return LLMContextFreshness(
                context_id, UNKNOWN, f"context {context_id!r} no longer exists"
            )

    def _compare(self, context_id: str, provenance) -> LLMContextFreshness:
        if provenance.source_type == "context_version":
            return self._check_context_version(context_id, provenance)
        if provenance.source_type == "research_artifact":
            return self._check_research_artifact(context_id, provenance)
        if provenance.source_type == "project_context":
            return self._check_project_context(context_id, provenance)

        # "external": nothing in the repository can verify this
        return LLMContextFreshness(
            context_id,
            UNKNOWN,
            "source_type 'external' cannot be verified against anything the "
            "repository tracks",
        )

    def _check_context_version(self, context_id: str, provenance) -> LLMContextFreshness:
        version_service = self.provenance_service.version_service
        if version_service is None:
            return LLMContextFreshness(
                context_id, UNKNOWN, "no version service is wired to compare against"
            )

        try:
            latest = version_service.latest(provenance.source_id)
        except UnknownContextVersionError:
            return LLMContextFreshness(
                context_id,
                UNKNOWN,
                f"context {provenance.source_id!r} has no recorded versions",
            )

        if latest.version == provenance.source_version:
            return LLMContextFreshness(
                context_id, FRESH, f"matches latest recorded version {latest.version}"
            )
        return LLMContextFreshness(
            context_id,
            STALE,
            f"provenance references version {provenance.source_version}, latest "
            f"recorded is {latest.version}",
        )

    def _check_research_artifact(self, context_id: str, provenance) -> LLMContextFreshness:
        artifact_store = self.provenance_service.artifact_store
        if artifact_store is None:
            return LLMContextFreshness(
                context_id, UNKNOWN, "no artifact store is wired to compare against"
            )

        artifact = artifact_store.get(provenance.source_id)
        if artifact is None:
            return LLMContextFreshness(
                context_id,
                UNKNOWN,
                f"research artifact {provenance.source_id!r} no longer exists",
            )

        if provenance.source_version is None:
            return LLMContextFreshness(
                context_id, UNKNOWN, "provenance recorded no source_version to compare"
            )

        if artifact.version == provenance.source_version:
            return LLMContextFreshness(
                context_id, FRESH, f"matches current artifact version {artifact.version}"
            )
        return LLMContextFreshness(
            context_id,
            STALE,
            f"provenance references version {provenance.source_version}, current "
            f"artifact version is {artifact.version}",
        )

    def _check_project_context(self, context_id: str, provenance) -> LLMContextFreshness:
        try:
            source = self.context_service.get(provenance.source_id)
        except UnknownProjectContextError:
            return LLMContextFreshness(
                context_id,
                UNKNOWN,
                f"source context {provenance.source_id!r} no longer exists",
            )

        if source.updated_at > provenance.created_at:
            return LLMContextFreshness(
                context_id,
                STALE,
                f"source context {provenance.source_id!r} was updated at "
                f"{source.updated_at.isoformat()}, after provenance was recorded "
                f"at {provenance.created_at.isoformat()}",
            )
        return LLMContextFreshness(
            context_id,
            FRESH,
            f"source context {provenance.source_id!r} is unchanged since provenance "
            "was recorded",
        )
