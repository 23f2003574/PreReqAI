import dataclasses
from copy import deepcopy

from ..context import estimate_text_tokens
from ..context_selection import content_text, content_tokens

# Context types that must never be dropped or truncated -- the system's own
# instructions to the model, as opposed to the facts/summaries/preferences
# it is reasoning over. Mirrors Commit #1's VALID_CONTEXT_TYPES vocabulary.
PROTECTED_CONTEXT_TYPES = frozenset({"system_prompt", "instruction"})

# Marks content that has been shrunk to fit a budget. Same idea as
# backend.llm.tool_results' truncation envelope -- a fixed, small marker so
# a reader always knows a preview stands in for the full content -- kept as
# a plain suffix here (rather than a JSON envelope) because compaction
# operates on arbitrary content, not a single tool's structured output.
_COMPACTED_SUFFIX = " …[compacted]"


class LLMContextCompactionService:
    """Compresses an already-selected set of project context to fit a token budget.

    Reuses Commit #4's content_tokens()/content_text() for sizing -- no
    second token-management system -- and shrinks oversized entries the way
    backend.llm.tool_results.LLMToolResultService already shrinks an
    over-budget tool output: a preview kept just large enough to fit,
    rather than the entry being silently dropped. Never reads from or
    writes to a store, and never mutates the LLMProjectContext objects it
    is given -- every returned entry is either an untouched deep copy or a
    brand new object built via dataclasses.replace.
    """

    def estimate(self, context: list) -> int:
        """Total estimated tokens across every entry in `context`."""
        return sum(content_tokens(entry) for entry in context)

    def preserve(self, context: list, items) -> list:
        """Entries of `context` that must be kept intact.

        That is every entry named in `items` (by context_id or object),
        plus every system_prompt/instruction entry -- Commit #5's rule that
        this content is never compacted away, regardless of what the caller
        asked to preserve.
        """
        ids = {item.context_id if hasattr(item, "context_id") else item for item in items}
        return [
            entry
            for entry in context
            if entry.context_id in ids or entry.context_type in PROTECTED_CONTEXT_TYPES
        ]

    def compact(self, context: list, token_budget: int) -> list:
        """Fit `context` under `token_budget`, compressing before dropping.

        Below budget: returned unchanged (as deep copies). Over budget:
        protected entries (system/instruction, plus anything carrying
        metadata["priority"] == "high") are allocated space first, in their
        original order; the rest are ordered newest-first, so the oldest --
        the most likely to be redundant -- are the first compacted or, if
        even a minimal preview will not fit, dropped. The budget is never
        exceeded.
        """
        if not isinstance(token_budget, int) or isinstance(token_budget, bool) or token_budget <= 0:
            raise ValueError("token_budget must be a positive integer")

        if not context:
            return []

        if self.estimate(context) <= token_budget:
            return [deepcopy(entry) for entry in context]

        high_priority_ids = [
            entry.context_id for entry in context if entry.metadata.get("priority") == "high"
        ]
        protected = self.preserve(context, high_priority_ids)
        protected_ids = {entry.context_id for entry in protected}

        # newest first, so budget is allocated to the freshest (least likely
        # redundant) entries preferentially -- older entries are further
        # back in the queue and are the first compacted or dropped
        remainder = sorted(
            (entry for entry in context if entry.context_id not in protected_ids),
            key=lambda entry: (-entry.updated_at.timestamp(), entry.context_id),
        )

        compacted = []
        used = 0
        for entry in [*protected, *remainder]:
            remaining_budget = token_budget - used
            if remaining_budget <= 0:
                break

            tokens = content_tokens(entry)
            if tokens <= remaining_budget:
                compacted.append(deepcopy(entry))
                used += tokens
                continue

            shrunk = self._shrink_to_fit(entry, remaining_budget)
            if shrunk is None:
                break
            compacted.append(shrunk)
            used += content_tokens(shrunk)

        return compacted

    @staticmethod
    def _shrink_to_fit(entry, remaining_budget: int):
        """A copy of `entry` whose content is a preview fitting `remaining_budget`.

        None if even an empty preview plus the compaction marker would not
        fit -- there is nothing useful left to say about this entry within
        the budget that remains.
        """
        suffix_tokens = estimate_text_tokens(_COMPACTED_SUFFIX)
        if suffix_tokens > remaining_budget:
            return None

        original_text = content_text(entry)
        original_tokens = estimate_text_tokens(original_text)

        keep_chars = max(0, (remaining_budget - suffix_tokens) * 4)
        while True:
            preview = original_text[:keep_chars] + _COMPACTED_SUFFIX
            if estimate_text_tokens(preview) <= remaining_budget or keep_chars == 0:
                break
            keep_chars = keep_chars * 3 // 4

        return dataclasses.replace(
            entry,
            content=preview,
            metadata={
                **entry.metadata,
                "compacted": True,
                "original_estimated_tokens": original_tokens,
            },
        )
