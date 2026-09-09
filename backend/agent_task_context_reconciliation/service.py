from backend.agent_policy_engine import DENY, LLMAgentPolicyEvaluator
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.llm.context_freshness import STALE, LLMContextFreshnessService
from backend.llm.project_context import LLMProjectContextService, UnknownProjectContextError

from .models import ContextReconciliationResult


class InvalidContextReconciliationError(ValueError):
    """Raised when reconcile() is given a missing/blank agent_id or scope_id."""


class TaskContextReconciliationScopeMismatchError(ValueError):
    """Raised when task_id does not belong to agent_id in scope_id."""


class LLMAgentTaskContextReconciler:
    """Compares one task's stored relevant_context against what is
    currently resolvable and reports what would change -- without
    changing anything.

    Not a second resolver: discovering genuinely *new* sources is
    entirely Commit #2's own backend.agent_task_context_resolution.
    LLMAgentTaskContextResolver.resolve() (a required collaborator --
    reconciliation's whole purpose is comparing against what that
    resolver currently says). It is deliberately NOT used to verify the
    *stored* side, though: Commit #2's own Rule #1 ("start with the
    task's explicit context") makes resolve() carry every already-stored
    relevant_context entry straight through unconditionally, never
    re-checking its authorization, freshness, or current content -- so a
    stale, now-unauthorized, or edited stored entry would always come
    back looking unchanged if compared against resolve()'s own
    selected_context. Verifying the stored side instead reuses the exact
    same underlying rule engines Commit #2's resolver itself is built
    from -- backend.agent_policy_engine/backend.agent_policy_resolution
    for authorization (mirroring LLMAgentTaskContextResolver.
    _authorization_denial()'s own pattern, same "explicit deny wins"
    posture, reimplemented locally rather than a private cross-module
    import), backend.llm.context_freshness.LLMContextFreshnessService
    for staleness (unchanged, the same optional collaborator shape
    Commit #5/#7 already use), and a direct backend.llm.project_context.
    LLMProjectContextService.get() read for content drift/existence --
    applied independently to every stored entry, not filtered through
    resolve()'s own explicit-passthrough behavior.

    project_context_service/freshness_service/policy_service are all
    optional: omitting any of them narrows what reconciliation can
    detect (no live content to diff against, no staleness verdict, no
    authorization check) but never makes reconcile() fail or invent a
    false difference.

    reconcile() only ever reads -- task_context_service.get(),
    resolver.resolve(), and whatever the optional collaborators read
    internally. It never calls update()/snapshot() on the task context,
    and never touches a project context or memory store's own write
    path; every difference it reports is left for a caller to act on (or
    not) separately, e.g. via Commit #7's own
    LLMAgentTaskContextRefreshService.
    """

    def __init__(
        self,
        task_context_service: LLMAgentTaskContextService,
        resolver: LLMAgentTaskContextResolver,
        project_context_service: LLMProjectContextService = None,
        freshness_service: LLMContextFreshnessService = None,
        policy_service=None,
    ):
        self._task_context_service = task_context_service
        self._resolver = resolver
        self._project_context_service = project_context_service
        self._freshness_service = freshness_service
        self._policy_resolver = LLMAgentPolicyResolver(policy_service) if policy_service is not None else None
        self._policy_evaluator = LLMAgentPolicyEvaluator() if policy_service is not None else None

    def reconcile(self, task_id: str, agent_id: str, scope_id: str) -> ContextReconciliationResult:
        """Compare task_id's stored relevant_context against what is
        currently resolvable for agent_id in scope_id.

        Raises:
            InvalidContextReconciliationError: If agent_id or scope_id is
                missing/blank
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get(), unwrapped)
            TaskContextReconciliationScopeMismatchError: If task_id does
                not belong to agent_id in scope_id
        """
        self._validate(agent_id, scope_id)

        task_context = self._task_context_service.get(task_id)
        if task_context.agent_id != agent_id or task_context.scope_id != scope_id:
            raise TaskContextReconciliationScopeMismatchError(
                f"task {task_id!r} belongs to agent {task_context.agent_id!r} in scope "
                f"{task_context.scope_id!r}, not agent {agent_id!r} in scope {scope_id!r}"
            )

        resolved = self._resolver.resolve(task_id, agent_id, scope_id)

        stored_by_id = {
            entry["context_id"]: entry for entry in task_context.relevant_context if entry.get("context_id")
        }
        stored_provenance_by_id = self._provenance_by_id(task_context.provenance)

        added = self._added(stored_by_id, resolved)

        removed = []
        changed = []
        unchanged = []
        conflicts = []

        for context_id in sorted(stored_by_id):
            stored_entry = stored_by_id[context_id]
            stored_provenance = stored_provenance_by_id.get(context_id)
            item = self._item(context_id, stored_entry, stored_provenance_by_id)

            live_context, gone = self._live_context(context_id)
            if gone:
                removed.append(item)
                continue

            denial_reason = self._authorization_denial(
                agent_id, scope_id, context_id, stored_entry.get("context_type")
            )
            if denial_reason is not None:
                conflicts.append({"context_id": context_id, "reason": denial_reason, "entry": stored_entry, "provenance": stored_provenance})
                removed.append(item)
                continue

            if live_context is not None and stored_entry.get("content") != live_context.content:
                changed.append(
                    {
                        "context_id": context_id,
                        "stored_entry": stored_entry,
                        "fresh_entry": live_context.to_dict(),
                        "stored_provenance": stored_provenance,
                        "fresh_provenance": stored_provenance,
                    }
                )
            else:
                unchanged.append(item)

        stale = sorted(self._stale_ids(task_context, stored_provenance_by_id))

        return ContextReconciliationResult(
            task_id=task_id,
            agent_id=agent_id,
            scope_id=scope_id,
            added=added,
            removed=removed,
            changed=changed,
            unchanged=unchanged,
            stale=stale,
            conflicts=conflicts,
        )

    # -- internals ------------------------------------------------------------

    def _added(self, stored_by_id: dict, resolved) -> list:
        fresh_provenance_by_id = self._provenance_by_id(resolved.provenance)
        added_ids = {
            entry["context_id"]
            for entry in resolved.selected_context
            if entry.get("context_id") and entry["context_id"] not in stored_by_id
        }
        fresh_by_id = {entry["context_id"]: entry for entry in resolved.selected_context if entry.get("context_id")}
        return [self._item(context_id, fresh_by_id[context_id], fresh_provenance_by_id) for context_id in sorted(added_ids)]

    def _live_context(self, context_id):
        """(live LLMProjectContext or None, gone: bool). gone is only ever
        True when a project_context_service is actually wired in and the
        source has genuinely vanished from it; with no collaborator
        supplied, nothing can be judged "gone" at all."""
        if self._project_context_service is None:
            return None, False
        try:
            return self._project_context_service.get(context_id), False
        except UnknownProjectContextError:
            return None, True

    def _authorization_denial(self, agent_id, scope_id, context_id, context_type):
        if self._policy_resolver is None:
            return None

        action = {
            "agent_id": agent_id,
            "scope_id": scope_id,
            "context_id": context_id,
            "context_type": context_type,
        }
        for resolved_policy in self._policy_resolver.resolve(scope_id):
            decision = self._policy_evaluator.evaluate(resolved_policy.policy, action)
            if decision.rule_id is not None and decision.effect == DENY:
                return (
                    f"context {context_id!r} denied for agent {agent_id!r} in scope {scope_id!r} by "
                    f"policy {decision.policy_id!r} rule {decision.rule_id!r}: {decision.reason}"
                )
        return None

    def _stale_ids(self, task_context, provenance_by_id) -> set:
        if self._freshness_service is None:
            return set()

        stale = set()
        for entry in task_context.relevant_context:
            context_id = entry.get("context_id")
            if not context_id:
                continue

            provenance = provenance_by_id.get(context_id)
            if provenance is None or provenance.source_type != "project_context":
                continue

            try:
                result = self._freshness_service.check(context_id)
            except UnknownProjectContextError:
                stale.add(context_id)
                continue

            if result.status == STALE:
                stale.add(context_id)

        return stale

    @staticmethod
    def _item(context_id, entry, provenance_by_id) -> dict:
        return {
            "context_id": context_id,
            "entry": entry,
            "provenance": provenance_by_id.get(context_id),
        }

    @staticmethod
    def _provenance_by_id(provenance: list) -> dict:
        by_id = {}
        for record in provenance:
            by_id[record.context_id] = record  # last (most recent) wins
        return by_id

    @staticmethod
    def _validate(agent_id, scope_id) -> None:
        if not agent_id or not isinstance(agent_id, str):
            raise InvalidContextReconciliationError("agent_id is required and must be a non-empty string")
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidContextReconciliationError("scope_id is required and must be a non-empty string")
