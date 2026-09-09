from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedAgentTaskContext:
    """LLMAgentTaskContextResolver.resolve()'s complete, provenance-preserving
    outcome for one (task_id, agent_id, scope_id) request.

    task_context is Commit #1's own LLMAgentTaskContext record, verbatim.
    selected_context always starts with task_context.relevant_context
    (Rule: "start with the task's explicit context/constraints") and may
    hold additional dicts pulled in through existing retrieval/selection/
    compaction; excluded_context holds candidates that were considered but
    left out (already present, stale, unauthorized, or not relevant/over
    budget) -- each in the same dict shape as selected_context, never
    silently dropped. selected_memories is Commit #1-adjacent
    backend.agent_execution_memory.LLMAgentMemory records, verbatim,
    included only when a memory service/retriever was actually wired in.

    provenance is task_context.provenance's own trail plus one
    backend.llm.context_provenance.LLMContextProvenance per newly
    included context/memory entry -- append-only in spirit, but this
    result itself is never persisted back onto task_context (resolve()
    is read-only).

    resolution_reasons maps every considered item's own id (a context_id
    or memory_id -- distinct id spaces from distinct generators, so
    collisions are not a practical concern) to a human-readable account
    of the decision, the same "never silently imply a decision"
    discipline backend.agent_capability_resolution.ResolvedAgentCapabilities
    already keeps; task_context's own explicit entries are carried over
    unconditionally (no per-item decision was made about them), so they
    are covered by a single aggregate "__task_context__" reason instead.
    """

    task_id: str
    agent_id: str
    scope_id: str
    task_context: object
    selected_context: list
    selected_memories: list
    excluded_context: list
    provenance: list
    resolution_reasons: dict
