from threading import RLock

from backend.agent_policy_engine import ACTIVE, LLMAgentPolicyService

from .models import ResolvedPolicy


class PolicyPrecedenceError(ValueError):
    """Raised when set_precedence() is given an invalid pair, or a pair
    that would create a precedence cycle."""


class UnknownExecutionScopeError(ValueError):
    """Raised by resolve_for_execution() when execution_id cannot be
    mapped to a scope_id -- either this resolver was never configured
    with scope_for_execution, or it returned no scope for this
    execution_id."""


class LLMAgentPolicyResolver:
    """Resolves every Commit #1 ACTIVE policy applicable to a scope --
    or, via resolve_for_execution(), to one already-completed execution
    -- into one deterministically ordered list, ready for
    LLMAgentPolicyEvaluator.evaluate() to run down in that order.

    Not a second policy-resolution framework: precedence bookkeeping and
    ordering follow the exact model
    backend.session.execution_policy_precedence_service.ExecutionPolicyPrecedenceService
    already established for the repo's other allow/deny domain --
    set_precedence() records that one policy explicitly outranks another
    (rejecting a rule that would create a cycle, directly or
    transitively), and resolve() reorders a scope's policies, already in
    their baseline creation order, so every recorded rule is honored
    while any pair with no rule between them, direct or transitive, keeps
    its original relative order. This is a from-scratch, same-shape
    reimplementation local to this module rather than an import of that
    session-layer service, which governs an unrelated domain (execution
    network/artifact/recovery policy for the research workspace) that
    this module has no business depending on.

    "project/task/default" precedence, where a caller's own domain
    actually has such a hierarchy, is expressed through this same
    explicit set_precedence(policy_id, higher_than=...) mechanism -- e.g.
    a caller can record that a task-level policy outranks a
    project-level default -- rather than this resolver inventing a
    second, implicit naming convention for scope nesting. Commit #1's
    LLMAgentPolicy.scope_id stays a single, flat identifier; no new
    policy language is introduced here.

    Policy lookup is entirely
    LLMAgentPolicyService.list(scope_id, status=ACTIVE) -- resolve()
    never reads a store directly and never mutates a policy. ARCHIVED
    policies never participate in resolution at all: they are retired,
    per Commit #1's own semantics, exactly as an ARCHIVED policy already
    denies unconditionally in LLMAgentPolicyEvaluator.

    resolve_for_execution() derives scope_id from execution_id via
    scope_for_execution, a plain callable supplied by the caller (default
    None). There is no existing execution-to-scope index anywhere in this
    repository -- an LLMAgentPlanExecution/LLMAgentPlan carries no
    scope_id at all -- so this is the integration seam a caller who does
    know that mapping (e.g. the session/notebook layer that started the
    execution) is expected to supply, the same duck-typed-collaborator
    delegation ExecutionPolicyPrecedenceService.__init__ already uses for
    its own execution_policy_assignment_service.

    The service is thread-safe: precedence bookkeeping and ordering are
    guarded by an internal lock.
    """

    def __init__(self, policy_service: LLMAgentPolicyService, scope_for_execution=None):
        """
        Args:
            policy_service: The Commit #1 LLMAgentPolicyService used to
                list a scope's ACTIVE policies
            scope_for_execution: Optional callable, execution_id ->
                scope_id, used only by resolve_for_execution()
        """
        self._policy_service = policy_service
        self._scope_for_execution = scope_for_execution
        self._outranks = {}
        self._lock = RLock()

    def set_precedence(self, policy_id: str, higher_than: str) -> None:
        """Record that policy_id outranks higher_than for resolution
        ordering purposes.

        Raises:
            PolicyPrecedenceError: If policy_id or higher_than is empty
                or blank, policy_id equals higher_than, or the rule would
                create a precedence cycle (higher_than already, directly
                or transitively, outranks policy_id)
        """
        if not policy_id or not isinstance(policy_id, str):
            raise PolicyPrecedenceError("policy_id must be a non-empty string")
        if not higher_than or not isinstance(higher_than, str):
            raise PolicyPrecedenceError("higher_than must be a non-empty string")
        if policy_id == higher_than:
            raise PolicyPrecedenceError(f"policy {policy_id!r} cannot be declared to outrank itself")

        with self._lock:
            if self._reachable(higher_than, policy_id):
                raise PolicyPrecedenceError(
                    f"cannot record that {policy_id!r} outranks {higher_than!r}: "
                    f"{higher_than!r} already outranks {policy_id!r}, directly or transitively"
                )
            self._outranks.setdefault(policy_id, set()).add(higher_than)

    def _reachable(self, start: str, target: str) -> bool:
        if start == target:
            return True
        visited = {start}
        queue = [start]
        while queue:
            current = queue.pop()
            for neighbor in self._outranks.get(current, ()):
                if neighbor == target:
                    return True
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    def _ordered(self, policies: list) -> list:
        """policies, already in baseline (creation) order, reordered so
        every recorded set_precedence() rule between two of them is
        honored -- any pair with no rule, direct or transitive, keeps its
        original relative order. Exactly
        ExecutionPolicyPrecedenceService.resolve()'s own topological-sort
        shape, reused here rather than reinvented."""
        ids = [policy.policy_id for policy in policies]
        by_id = {policy.policy_id: policy for policy in policies}
        id_set = set(ids)
        position = {policy_id: index for index, policy_id in enumerate(ids)}

        with self._lock:
            successors = {
                policy_id: [higher_than for higher_than in self._outranks.get(policy_id, ()) if higher_than in id_set]
                for policy_id in ids
            }

        in_degree = {policy_id: 0 for policy_id in ids}
        for policy_id in ids:
            for higher_than in successors[policy_id]:
                in_degree[higher_than] += 1

        remaining = set(ids)
        ordered_ids = []
        while remaining:
            ready = [policy_id for policy_id in remaining if in_degree[policy_id] == 0]
            next_id = min(ready, key=lambda policy_id: position[policy_id])
            ordered_ids.append(next_id)
            remaining.remove(next_id)
            for higher_than in successors[next_id]:
                if higher_than in remaining:
                    in_degree[higher_than] -= 1

        return [by_id[policy_id] for policy_id in ordered_ids]

    def resolve(self, scope_id: str, context: dict = None) -> list:
        """Every ACTIVE policy for scope_id, deterministically ordered by
        precedence (index 0 = highest).

        context is accepted for forward compatibility with callers that
        want to record why a resolution was requested, and does not
        narrow which policies are returned -- every ACTIVE policy in
        scope_id applies; Commit #1's LLMAgentPolicyEvaluator (not this
        resolver) is what decides whether any of its rules actually match
        a given action.

        Never crosses a scope boundary: only policies whose own scope_id
        is exactly scope_id are ever returned, exactly Commit #1's own
        LLMAgentPolicyService.list() isolation.

        Raises:
            InvalidAgentPolicyError: If scope_id is missing (propagated
                from LLMAgentPolicyService.list(), not wrapped)
            ValueError: If context is given and is not a dict
        """
        if context is not None and not isinstance(context, dict):
            raise ValueError("context must be a dict when given")

        policies = self._policy_service.list(scope_id, status=ACTIVE)
        ordered = self._ordered(policies)
        return [
            ResolvedPolicy(policy=policy, precedence=index, source=f"scope:{scope_id}")
            for index, policy in enumerate(ordered)
        ]

    def resolve_for_execution(self, execution_id: str, context: dict = None) -> list:
        """resolve() the policies applicable to the scope that owns
        execution_id, via scope_for_execution.

        Raises:
            UnknownExecutionScopeError: If this resolver was built
                without scope_for_execution, or it returns no scope_id
                for execution_id
        """
        if self._scope_for_execution is None:
            raise UnknownExecutionScopeError(
                "this resolver was not configured with scope_for_execution; "
                "cannot resolve a scope from execution_id alone"
            )

        scope_id = self._scope_for_execution(execution_id)
        if not scope_id:
            raise UnknownExecutionScopeError(
                f"scope_for_execution returned no scope for execution {execution_id!r}"
            )

        return self.resolve(scope_id, context=context)
