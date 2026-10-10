from dataclasses import dataclass


@dataclass(frozen=True)
class AgentContextPackage:
    """LLMAgentTaskContextPackager.package()'s final, request-ready bundle
    for one budgeted task context.

    task carries the task's own identity/framing (task_id/agent_id/
    scope_id/objective/inputs) -- never reshaped, only gathered from
    Commit #1's own LLMAgentTaskContext. constraints is that same
    record's own constraints list, verbatim (Rule: "preserve the task
    objective and explicit constraints").

    context is a list of messages in the exact {"role", "content",
    "metadata"} envelope backend.llm.context_injection.
    LLMContextInjectionService._message_for() already establishes for
    injecting project context into a real LLMRequest -- reused here so a
    caller can fold this list straight into an LLMRequest.messages the
    same way inject() does, rather than a second prompt/message format.
    Built only from Commit #3's own selected_context (Rule: "include
    only context surviving the budgeting stage") -- dropped_context is
    never read here.

    memories is Commit #2's own selected_memories (via Commit #3's
    additive pass-through), each rendered with LLMAgentMemory.to_dict() --
    no message envelope invented for it, since nothing in this
    repository already has one for memory.

    provenance is Commit #3's own provenance list, rendered as plain
    dicts (Rule: "maintain source/provenance metadata through
    packaging") -- covers every context/memory entry ever injected into
    this task's resolution, including ones dropped_context/budgeting
    later excluded, exactly as Commit #1/#2/#3 already established.

    metadata carries packaging-level bookkeeping (identity plus Commit
    #3's own budget/estimated_tokens/truncation_applied) and, when given,
    the caller-supplied request_context under its own "request_context"
    key -- never merged in a way that could shadow this service's own
    identity fields.
    """

    task: dict
    constraints: list
    context: list
    memories: list
    provenance: list
    metadata: dict
