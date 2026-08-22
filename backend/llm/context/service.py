from .models import LLMContext, LLMContextItem


class UnknownContextError(KeyError):
    """Raised when looking up a context_id that has not been created."""


class LLMContextService:
    """Assembles the structured context (system + prioritized items) for an LLM call.

    build() emits messages as {"role": item.type, "content": item.content} dicts --
    the same shape backend.llm.LLMRequest.messages (Commit #1) expects -- so the
    result can be passed straight into an LLMRequest once routing (Commit #3)
    has picked a provider/model.
    """

    def __init__(self):
        self._contexts = {}
        self._counters = {}

    def create(self, request_id, system=None, metadata=None, token_budget=None) -> LLMContext:
        if not request_id or not isinstance(request_id, str):
            raise ValueError("request_id is required")

        if request_id in self._contexts:
            raise ValueError(f"a context already exists for request_id {request_id!r}")

        if token_budget is not None and token_budget <= 0:
            raise ValueError("token_budget must be a positive integer")

        context = LLMContext(
            request_id=request_id,
            system=system,
            messages=[],
            metadata=dict(metadata) if metadata else {},
            token_budget=token_budget,
        )
        self._contexts[request_id] = context
        self._counters[request_id] = 0
        return context

    def _get(self, context_id) -> LLMContext:
        try:
            return self._contexts[context_id]
        except KeyError:
            raise UnknownContextError(context_id)

    def add(self, context_id, item: LLMContextItem) -> LLMContextItem:
        item.validate()
        context = self._get(context_id)

        self._counters[context_id] += 1
        item.id = f"{context_id}-item-{self._counters[context_id]}"
        context.messages.append(item)
        return item

    def remove(self, context_id, item_id) -> LLMContextItem:
        context = self._get(context_id)

        for index, item in enumerate(context.messages):
            if item.id == item_id:
                del context.messages[index]
                return item

        raise KeyError(f"no context item {item_id!r} in context {context_id!r}")

    @staticmethod
    def _estimate_text_tokens(text) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    def estimate_tokens(self, context_id) -> int:
        """Deterministic token estimate for everything currently in the context."""
        context = self._get(context_id)

        total = self._estimate_text_tokens(context.system)
        for item in context.messages:
            total += self._estimate_text_tokens(item.content)
        return total

    def build(self, context_id) -> dict:
        """Assemble the final context payload, trimmed to fit the token budget.

        Items are ranked by priority (higher first, insertion order breaking
        ties) to decide what is retained, but the returned messages are
        emitted in their original insertion order.
        """
        context = self._get(context_id)

        system_tokens = self._estimate_text_tokens(context.system)
        budget = context.token_budget

        if budget is not None and system_tokens > budget:
            raise ValueError(
                f"token_budget {budget} is too small to include the system "
                f"prompt ({system_tokens} tokens)"
            )

        remaining_budget = None if budget is None else budget - system_tokens

        ranked = sorted(
            enumerate(context.messages),
            key=lambda pair: (-pair[1].priority, pair[0]),
        )

        kept_indices = set()
        used_tokens = 0
        for index, item in ranked:
            item_tokens = self._estimate_text_tokens(item.content)
            if remaining_budget is not None and used_tokens + item_tokens > remaining_budget:
                continue
            kept_indices.add(index)
            used_tokens += item_tokens

        messages = [
            {"role": item.type, "content": item.content}
            for index, item in enumerate(context.messages)
            if index in kept_indices
        ]

        return {
            "request_id": context.request_id,
            "system": context.system,
            "messages": messages,
            "metadata": dict(context.metadata),
            "estimated_tokens": system_tokens + used_tokens,
        }
