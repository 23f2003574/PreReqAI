from copy import deepcopy

from ..project_context import LLMProjectContextService
from .in_memory_store import InMemoryLLMContextVersionStore
from .models import LLMContextVersion
from .store import LLMContextVersionStore


class UnknownContextVersionError(KeyError):
    """Raised when get()/latest() names a context_id/version with no snapshot."""


class LLMContextVersionService:
    """Creates immutable, monotonically-numbered snapshots of a Commit #1 context.

    Reuses LLMProjectContextService (Commit #1) as the sole source of a
    context's current content and its scope isolation -- this service holds
    no content of its own, it only records what Commit #1 already has at the
    moment snapshot() is called. Persists through an LLMContextVersionStore
    (in-memory by default, or the JSON-file-backed store built on
    backend.storage.AtomicJsonFile), the same split Commit #1 already uses
    between store and service, rather than a second history system.
    """

    def __init__(
        self,
        context_service: LLMProjectContextService,
        store: LLMContextVersionStore = None,
    ):
        self.context_service = context_service
        self.store = store if store is not None else InMemoryLLMContextVersionStore()

    def snapshot(self, context_id: str) -> LLMContextVersion:
        """Record the context's current content as the next monotonic version.

        Raises UnknownProjectContextError (from Commit #1) if context_id
        does not exist -- this service never invents context identity, it
        only reads it.
        """
        context = self.context_service.get(context_id)

        previous = self.store.latest_for_context(context_id)
        next_version = 1 if previous is None else previous.version + 1

        version = LLMContextVersion(
            context_id=context_id,
            version=next_version,
            content=deepcopy(context.content),
        )
        return self.store.save(version)

    def get(self, context_id: str, version: int) -> LLMContextVersion:
        found = self.store.get(context_id, version)
        if found is None:
            raise UnknownContextVersionError((context_id, version))
        return found

    def history(self, context_id: str) -> list:
        return self.store.list_for_context(context_id)

    def latest(self, context_id: str) -> LLMContextVersion:
        found = self.store.latest_for_context(context_id)
        if found is None:
            raise UnknownContextVersionError(context_id)
        return found
