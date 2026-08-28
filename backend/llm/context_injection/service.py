import dataclasses

from ..context_compaction import LLMContextCompactionService
from ..context_provenance import LLMContextProvenanceService, UnknownProvenanceError
from ..context_retrieval import LLMContextRetrievalService
from ..context_selection import LLMContextSelectionService, content_text
from ..models import LLMRequest

# The message role an injected context item carries, the same way
# backend.llm.tool_results uses a dedicated TOOL_ROLE for tool output.
CONTEXT_ROLE = "context"


class LLMContextInjectionService:
    """Wires Commits #3-#6 into the existing LLMRequest/message pipeline.

    prepare() is retrieval -> selection -> compaction, in that order, so
    nothing reaches inject() that has not already been ranked for
    relevance (Commit #3), trimmed to the caller's token_budget
    (Commit #4), and, as a final safety net, compacted to guarantee that
    same budget (Commit #5) -- reusing the identical estimate_text_tokens
    accounting both of those already use, not a second one.

    inject() then folds the prepared contexts into an existing LLMRequest
    as extra messages, in the same {"role", "content"} shape
    backend.llm.context.LLMContextService.build() already emits for every
    other message, plus a "metadata" key carrying each context's identity
    and (Commit #6) provenance. build() itself is not called here: its
    output keeps only role/content, and routing through it would silently
    drop that metadata, which the Rules require to survive injection.
    Neither the source LLMRequest nor any LLMProjectContext is mutated --
    inject() only reads contexts and returns a new LLMRequest.
    """

    def __init__(
        self,
        retrieval_service: LLMContextRetrievalService,
        selection_service: LLMContextSelectionService,
        compaction_service: LLMContextCompactionService,
        provenance_service: LLMContextProvenanceService = None,
    ):
        self.retrieval_service = retrieval_service
        self.selection_service = selection_service
        self.compaction_service = compaction_service
        self.provenance_service = provenance_service

    def prepare(self, scope_id: str, task: str, token_budget: int) -> list:
        """Retrieve, select, and compact context for one scope/task/budget.

        Retrieval (Commit #3) never leaves scope_id -- it is backed by
        Commit #1's own scope-filtered list() -- so nothing outside the
        requested scope can reach selection or compaction, and therefore
        never reaches inject() either.
        """
        matches = self.retrieval_service.rank(scope_id, task)
        contexts = [match.context for match in matches]

        selected = self.selection_service.select(contexts, task, token_budget)
        return self.compaction_service.compact(selected, token_budget)

    def _provenance_metadata(self, context):
        if self.provenance_service is None:
            return None
        try:
            provenance = self.provenance_service.get(context.context_id)
        except UnknownProvenanceError:
            return None
        return {
            "source_type": provenance.source_type,
            "source_id": provenance.source_id,
            "source_version": provenance.source_version,
            "excerpt": provenance.excerpt,
        }

    def _message_for(self, context) -> dict:
        metadata = {
            "context_id": context.context_id,
            "scope_id": context.scope_id,
            "context_type": context.context_type,
        }
        provenance = self._provenance_metadata(context)
        if provenance is not None:
            metadata["provenance"] = provenance

        return {
            "role": CONTEXT_ROLE,
            "content": content_text(context),
            "metadata": metadata,
        }

    def inject(self, request: LLMRequest, contexts: list) -> LLMRequest:
        """Prepend `contexts` to `request` as new messages, changing nothing else.

        Existing messages are kept exactly as given, in their original
        order, after the injected context messages. `contexts` is expected
        to already have gone through prepare() (or at least select()/
        compact()); inject() trusts that budget and does not re-derive one
        of its own.
        """
        context_messages = [self._message_for(context) for context in contexts]
        combined_messages = context_messages + list(request.messages)
        return dataclasses.replace(request, messages=combined_messages)
