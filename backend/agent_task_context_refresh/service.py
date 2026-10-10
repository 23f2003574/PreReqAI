from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.llm.context_freshness import STALE, LLMContextFreshnessService
from backend.llm.project_context import UnknownProjectContextError

from .models import ContextRefreshResult


class InvalidContextRefreshError(ValueError):
    """Raised when refresh() is given a missing/blank task_id, or a
    non-string reason."""


class LLMAgentTaskContextRefreshService:
    """Re-resolves a task's own relevant_context in place, without
    touching the underlying project context or agent memory it was built
    from.

    Not a second refresh/versioning engine: staleness detection is
    backend.llm.context_freshness.LLMContextFreshnessService.check(),
    unchanged; discovering newly relevant sources is Commit #2's own
    backend.agent_task_context_resolution.LLMAgentTaskContextResolver.
    resolve() (which itself already composes backend.llm.
    context_retrieval/context_selection -- no retrieval/ranking logic is
    written here); persisting the refreshed relevant_context is Commit
    #1's own LLMAgentTaskContextService.update() (which already keeps
    provenance append-only and every other field untouched); and
    versioning is that same Commit #1's own snapshot() -- the
    "existing versioning mechanism" this commit's own Rule asks to
    reuse, not backend.llm.context_version.LLMContextVersionService
    (which snapshots a single backend.llm.project_context.
    LLMProjectContext's own content, a mismatched domain: a task's
    relevant_context is a composite of many sources, not one context_id).

    resolver and freshness_service are both optional collaborators (the
    same duck-typed "used only if given" shape every service in this
    series already uses): omitting resolver means no new source can ever
    be discovered (added_sources always empty); omitting
    freshness_service means nothing can ever be confirmed stale
    (stale_sources/removed_sources always empty) -- refresh() still
    succeeds either way, it simply has less to act on.

    refresh() computes everything (which sources are stale, which are
    new) before calling update() exactly once at the end -- if anything
    upstream raises (an unknown task_id, a resolver failure), update()
    is never reached and the task context is left exactly as it was
    (Rule/Test: "refresh failure leaves the previous context intact").
    Neither the project context store nor the memory store is ever
    written to here -- only ever read, through resolver/freshness_service.
    """

    def __init__(
        self,
        task_context_service: LLMAgentTaskContextService,
        resolver: LLMAgentTaskContextResolver = None,
        freshness_service: LLMContextFreshnessService = None,
    ):
        self._task_context_service = task_context_service
        self._resolver = resolver
        self._freshness_service = freshness_service

    def refresh(self, task_id: str, reason: str = None) -> ContextRefreshResult:
        """Re-resolve task_id's own relevant_context.

        Raises:
            InvalidContextRefreshError: If task_id is missing/blank, or
                reason is given and is not a string
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get(), unwrapped)
        """
        self._validate(task_id, reason)

        task_context = self._task_context_service.get(task_id)
        previous_snapshot = self._task_context_service.snapshot(task_id)

        current_context = list(task_context.relevant_context)
        current_ids = {entry.get("context_id") for entry in current_context if entry.get("context_id")}

        stale_ids = self._stale_ids(task_context)
        removed_sources = [entry for entry in current_context if entry.get("context_id") in stale_ids]

        added_sources = self._new_sources(task_context, current_ids)

        if not stale_ids and not added_sources:
            return ContextRefreshResult(
                task_id=task_id,
                refreshed=False,
                previous_context_version=previous_snapshot,
                new_context_version=previous_snapshot,
                added_sources=[],
                removed_sources=[],
                stale_sources=[],
                reason=reason,
            )

        kept = [entry for entry in current_context if entry.get("context_id") not in stale_ids]
        new_relevant_context = kept + added_sources

        self._task_context_service.update(task_id, {"relevant_context": new_relevant_context})
        new_snapshot = self._task_context_service.snapshot(task_id)

        return ContextRefreshResult(
            task_id=task_id,
            refreshed=True,
            previous_context_version=previous_snapshot,
            new_context_version=new_snapshot,
            added_sources=added_sources,
            removed_sources=removed_sources,
            stale_sources=sorted(stale_ids),
            reason=reason,
        )

    # -- internals ------------------------------------------------------------

    def _stale_ids(self, task_context) -> set:
        if self._freshness_service is None:
            return set()

        provenance_by_id = {}
        for record in task_context.provenance:
            provenance_by_id[record.context_id] = record  # last (most recent) wins

        stale = set()
        for entry in task_context.relevant_context:
            context_id = entry.get("context_id")
            if not context_id:
                continue

            provenance = provenance_by_id.get(context_id)
            if provenance is None or provenance.source_type != "project_context":
                continue  # nothing this freshness service can verify against

            try:
                result = self._freshness_service.check(context_id)
            except UnknownProjectContextError:
                stale.add(context_id)
                continue

            if result.status == STALE:
                stale.add(context_id)

        return stale

    def _new_sources(self, task_context, current_ids: set) -> list:
        if self._resolver is None:
            return []

        resolved = self._resolver.resolve(task_context.task_id, task_context.agent_id, task_context.scope_id)
        return [entry for entry in resolved.selected_context if entry.get("context_id") not in current_ids]

    @staticmethod
    def _validate(task_id, reason) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidContextRefreshError("task_id is required and must be a non-empty string")
        if reason is not None and not isinstance(reason, str):
            raise InvalidContextRefreshError("reason must be a string when given")
