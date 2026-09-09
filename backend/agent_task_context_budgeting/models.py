from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetedAgentTaskContext:
    """LLMAgentTaskContextBudgeter.budget()'s complete, provenance-preserving
    outcome for fitting one Commit #2 ResolvedAgentTaskContext's own
    selected_context under a token budget.

    task_context is Commit #1's own record, verbatim and untouched --
    budgeting never operates on task_context.inputs/constraints at all
    (Rule: "preserve mandatory task inputs and constraints"), so their
    survival is structural, not a side effect of anything this class does.

    selected_context/dropped_context are both in the same dict shape
    Commit #2's own ResolvedAgentTaskContext.selected_context already
    uses. An entry that survived but was shrunk to fit still appears in
    selected_context (never dropped_context) with metadata["compacted"]
    set -- backend.llm.context_compaction's own existing marker, reused
    as-is rather than inventing a second one.

    provenance is context.provenance, passed through unchanged: dropping
    a context entry from the current selected_context never invalidates
    or removes its own provenance record (Rule: "preserve provenance
    after compaction/truncation"), the same append-only, never-erased
    discipline Commit #1/#2 already established.

    reasons maps every considered context_id to a human-readable account
    of what budgeting did with it (kept unchanged / shrunk to fit /
    dropped), the same "never silently imply a decision" discipline
    every other *Result in this repository already keeps.

    selected_memories is context.selected_memories, passed through
    unchanged (added by Commit #4, additive): this commit's own Rules
    never asked for memory to be token-budgeted, only project context,
    so there is nothing to drop or shrink here -- but Commit #4's own
    packaging step needs a memories value on whatever it is given, and
    ResolvedAgentTaskContext is not itself Commit #4's second argument.
    """

    task_id: str
    agent_id: str
    scope_id: str
    task_context: object
    selected_context: list
    dropped_context: list
    estimated_tokens: int
    budget: int
    truncation_applied: bool
    reasons: dict
    provenance: list
    selected_memories: list
