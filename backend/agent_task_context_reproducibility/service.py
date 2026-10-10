from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_replay import LLMAgentTaskContextReplayService
from backend.agent_task_context_snapshots import LLMAgentTaskContextSnapshotService
from backend.llm.project_context import LLMProjectContextService, UnknownProjectContextError

from .models import BLOCKED, NON_REPRODUCIBLE, REPRODUCIBLE, TaskContextReproducibilityResult


class InvalidReproducibilityAssessmentError(ValueError):
    """Raised when assess() is given a missing/blank task_id or snapshot_id."""


class LLMAgentTaskContextReproducibilityService:
    """Determines whether a historical TaskContextSnapshot (Commit #10)
    can still be reconstructed exactly, from persisted data and current
    dependencies alone.

    Pure composition over this series' own already-completed pipeline,
    the orchestrator this whole series has been building toward:
    loading the snapshot, verifying its ownership, and checking its
    integrity is one call to Commit #11's own LLMAgentTaskContextReplayService.
    replay() (which itself already reuses Commit #5's integrity engine and
    Commit #10's own get()) -- not reimplemented here. Comparing the
    replayed context against the snapshot's own recorded ground truth
    reuses the same by-context_id, set-based comparison approach Commit
    #12's own diff service established (a local, same-shape
    implementation, since Commit #12's own diff() compares two *persisted*
    snapshot references, not an ad-hoc reconstructed list against one --
    a materially different calling shape, the same "reuse the pattern,
    not force a mismatched call" reasoning Commit #7/#10 already applied
    to backend.llm.context_version). Verifying that every provenance-
    referenced source is still available is a direct, minimal
    backend.llm.project_context.LLMProjectContextService.get() read per
    provenance record -- no new existence-checking mechanism.

    status is "blocked" whenever anything lands in blockers (Commit #11's
    own reused integrity findings, or a source this service itself found
    missing) -- these are reasons the reconstruction cannot be trusted at
    all. Otherwise, status is "non_reproducible" if the replayed context
    still differs from what the snapshot itself recorded, or
    "reproducible" if nothing at all is wrong. reproducible is True only
    for that last case.

    Rule "preserve task constraints and mandatory inputs exactly" is
    satisfied structurally: assess() never reads LLMAgentTaskContext.
    constraints/.inputs at all, and never calls update()/refresh()/
    restore() on anything -- every method it calls (replay(), get(),
    get() again) is itself already read-only. No LLM is ever invoked.
    Diagnostic text (blockers/differences) only ever names context_ids,
    never embeds raw content -- the same "reference by id, never quote
    the payload" discipline this service's own reused collaborators
    (Commit #5's secret-content screening, Commit #11's replay) already
    keep.
    """

    def __init__(
        self,
        task_context_service: LLMAgentTaskContextService,
        snapshot_service: LLMAgentTaskContextSnapshotService,
        project_context_service: LLMProjectContextService,
        replay_service: LLMAgentTaskContextReplayService = None,
    ):
        self._task_context_service = task_context_service
        self._snapshot_service = snapshot_service
        self._project_context_service = project_context_service
        self._replay_service = replay_service or LLMAgentTaskContextReplayService(
            task_context_service, snapshot_service
        )

    def assess(self, task_id: str, snapshot_id: str) -> TaskContextReproducibilityResult:
        """Assess whether snapshot_id can still be exactly reconstructed for task_id.

        Raises:
            InvalidReproducibilityAssessmentError: If task_id or
                snapshot_id is missing/blank
            UnknownTaskContextSnapshotError: If snapshot_id was never
                created (propagated from Commit #10's own get(), via
                Commit #11's replay(), unwrapped)
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get(), unwrapped)
            CrossTaskReplayError: If snapshot_id belongs to a different task
        """
        self._validate(task_id, snapshot_id)

        # Steps 1-3 (load + validate ownership/integrity + replay) are
        # entirely Commit #11's own job.
        replay_result = self._replay_service.replay(task_id, snapshot_id)

        # Re-read the snapshot for its own recorded ground truth --
        # already known to belong to task_id, since replay() above would
        # otherwise have raised.
        snapshot = self._snapshot_service.get(snapshot_id)
        resolved_context = snapshot.resolved_context if isinstance(snapshot.resolved_context, dict) else {}
        expected_context = [entry for entry in resolved_context.get("context", []) if isinstance(entry, dict)]
        replayed_context = list(replay_result.context)

        # Step 4: every source a provenance record names must still exist.
        source_versions_available, missing_sources = self._check_source_availability(snapshot.provenance)

        # provenance completeness: every expected entry has its own record.
        provenance_complete = self._check_provenance_complete(expected_context, snapshot.provenance)

        integrity_valid = replay_result.reproducible

        # Step 5: compare replayed vs expected using the same by-id,
        # set-based approach Commit #12's own diff service established.
        differences = self._diff_context(expected_context, replayed_context)

        blockers = list(replay_result.differences)
        blockers.extend(missing_sources)

        if blockers:
            status = BLOCKED
        elif differences:
            status = NON_REPRODUCIBLE
        else:
            status = REPRODUCIBLE

        return TaskContextReproducibilityResult(
            status=status,
            task_id=task_id,
            snapshot_id=snapshot_id,
            reproducible=(status == REPRODUCIBLE),
            replayed_context=replayed_context,
            expected_context=expected_context,
            differences=differences,
            provenance_complete=provenance_complete,
            source_versions_available=source_versions_available,
            integrity_valid=integrity_valid,
            blockers=blockers,
        )

    # -- internals ------------------------------------------------------------

    def _check_source_availability(self, provenance) -> tuple:
        missing = []
        for record in provenance:
            if record.source_type != "project_context":
                continue
            try:
                self._project_context_service.get(record.source_id)
            except UnknownProjectContextError:
                missing.append(
                    f"source {record.source_id!r} (referenced by provenance for context "
                    f"{record.context_id!r}) is no longer available"
                )
        return (len(missing) == 0), missing

    @staticmethod
    def _check_provenance_complete(expected_context, provenance) -> bool:
        provenance_ids = {record.context_id for record in provenance}
        for entry in expected_context:
            context_id = entry.get("context_id")
            if context_id and context_id not in provenance_ids:
                return False
        return True

    @staticmethod
    def _diff_context(expected, replayed) -> list:
        expected_by_id = {entry["context_id"]: entry for entry in expected if entry.get("context_id")}
        replayed_by_id = {entry["context_id"]: entry for entry in replayed if entry.get("context_id")}

        differences = []
        for context_id in sorted(set(expected_by_id) - set(replayed_by_id)):
            differences.append(
                f"context {context_id!r} is present in the snapshot but missing from the replayed context"
            )
        for context_id in sorted(set(replayed_by_id) - set(expected_by_id)):
            differences.append(
                f"context {context_id!r} is present in the replayed context but not in the snapshot"
            )
        for context_id in sorted(set(expected_by_id) & set(replayed_by_id)):
            if expected_by_id[context_id].get("content") != replayed_by_id[context_id].get("content"):
                differences.append(f"context {context_id!r} content differs between the snapshot and the replay")
        return differences

    @staticmethod
    def _validate(task_id, snapshot_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidReproducibilityAssessmentError("task_id is required and must be a non-empty string")
        if not snapshot_id or not isinstance(snapshot_id, str):
            raise InvalidReproducibilityAssessmentError("snapshot_id is required and must be a non-empty string")
