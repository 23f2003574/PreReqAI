import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone

from backend.llm.secret_redaction import LLMSecretRedactionService

from .in_memory_store import InMemoryExecutionStore
from .models import FAILED, RUNNING, SUCCEEDED, TERMINAL_STATUSES, LLMAgentCapabilityExecution
from .store import ExecutionStore

_redactor = LLMSecretRedactionService()


def _reference_for(value) -> str:
    """A short, non-reversible reference standing in for value -- never
    the value itself.

    value is first passed through the repository's own canonical
    backend.llm.secret_redaction.LLMSecretRedactionService (defense in
    depth: even a secret nested deep in a structure can never itself
    reach storage, since only a hash of the redacted form is ever kept),
    then rendered as one canonical JSON string
    (backend.llm.context_retrieval.searchable_text's own
    json.dumps(sort_keys=True, default=str) convention, reused here for
    the same "render structured content as one deterministic string"
    purpose) and hashed. This is the same "a short string identifies
    content without embedding it" idea
    backend.llm.response_cache.LLMCacheEntry.request_hash already uses
    for cache-key identity, applied here for genuine data minimization:
    the reference can be compared for equality but never turned back
    into the original payload.
    """
    redacted = _redactor.redact(value)
    canonical = json.dumps(redacted, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class InvalidCapabilityExecutionError(ValueError):
    """Raised when start()/fail() is given a missing/blank required
    field."""


class UnknownCapabilityExecutionError(KeyError):
    """Raised when get()/complete()/fail() is given an execution_id that
    was never started."""


class TerminalCapabilityExecutionError(ValueError):
    """Raised when complete()/fail() is given an execution_id that is
    already SUCCEEDED or FAILED -- a terminal record is retained history,
    never re-opened or overwritten by a second outcome (Rule: "terminal
    executions cannot be completed or failed again")."""


class LLMAgentCapabilityExecutionService:
    """Records the durable lifecycle of one attempt to use a Commit #1
    capability -- start() opens a RUNNING record, exactly one of
    complete()/fail() closes it. Never a second execution engine: this
    service calls nothing and runs nothing on behalf of the capability
    it records an attempt for (Rule: "this records execution; it does
    not execute capabilities") -- a caller starts a record, does
    whatever actually invoking the capability means on its own, and
    reports the outcome back.

    Persistence follows the exact save/get split every other store in
    this series already uses (an InMemoryExecutionStore by default, or a
    JSON-file-backed store built on the same backend.storage.
    AtomicJsonFile); status transitions are recorded the same
    replace-the-immutable-record-on-transition way
    backend.llm.tool_execution's own execution-record family already
    does, via dataclasses.replace(), never an in-place mutation.

    Raw input/output payloads are never persisted: _reference_for()
    (module-level, above) redacts through the repository's canonical
    backend.llm.secret_redaction.LLMSecretRedactionService and stores
    only a content hash. error text is redacted the same way but kept
    readable (never hashed away) -- the same "a short, redacted
    explanation, never a raw value" split
    backend.llm.tool_execution.LLMToolExecution.error/result already
    keeps, and the same reason LLMToolAudit deliberately omits a tool
    call's arguments/output entirely: neither is needed to know what was
    attempted, when, and how it ended, and either can carry credentials.
    """

    def __init__(self, store: ExecutionStore = None):
        self.store = store if store is not None else InMemoryExecutionStore()

    def start(
        self,
        agent_id: str,
        capability_id: str,
        capability_version: str,
        scope_id: str,
        input_data=None,
    ) -> LLMAgentCapabilityExecution:
        """Open a new RUNNING execution record.

        capability_version must be the exact Commit #1
        LLMAgentCapability.version in effect right now for capability_id
        -- captured verbatim here rather than re-derived later, so the
        record always names precisely which version was attempted (Rule:
        "execution records must identify the exact capability version
        used").

        input_data, when given, is never stored itself -- only
        input_reference, a content hash computed via this module's own
        _reference_for().

        Raises:
            InvalidCapabilityExecutionError: If agent_id, capability_id,
                capability_version, or scope_id is missing or blank
        """
        self._validate_id(agent_id, "agent_id")
        self._validate_id(capability_id, "capability_id")
        self._validate_id(capability_version, "capability_version")
        self._validate_id(scope_id, "scope_id")

        execution = LLMAgentCapabilityExecution(
            agent_id=agent_id,
            capability_id=capability_id,
            capability_version=capability_version,
            scope_id=scope_id,
            status=RUNNING,
            input_reference=None if input_data is None else _reference_for(input_data),
            output_reference=None,
            error=None,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
        )
        return self.store.save(execution)

    def complete(self, execution_id: str, result=None) -> LLMAgentCapabilityExecution:
        """Close execution_id as SUCCEEDED. result, when given, is never
        stored itself -- only output_reference, a content hash computed
        via this module's own _reference_for().

        Raises:
            UnknownCapabilityExecutionError: If execution_id was never
                started
            TerminalCapabilityExecutionError: If execution_id is already
                SUCCEEDED or FAILED
        """
        execution = self._require_running(execution_id)
        updated = replace(
            execution,
            status=SUCCEEDED,
            output_reference=None if result is None else _reference_for(result),
            completed_at=datetime.now(timezone.utc),
        )
        return self.store.save(updated)

    def fail(self, execution_id: str, error) -> LLMAgentCapabilityExecution:
        """Close execution_id as FAILED with a short, redacted error.

        error may be an exception or a string; either way it is rendered
        with str() and passed through the repository's canonical
        secret-redaction service before being stored.

        Raises:
            UnknownCapabilityExecutionError: If execution_id was never
                started
            TerminalCapabilityExecutionError: If execution_id is already
                SUCCEEDED or FAILED
            InvalidCapabilityExecutionError: If error is missing or
                renders to a blank string
        """
        execution = self._require_running(execution_id)

        error_text = str(error) if error is not None else ""
        if not error_text.strip():
            raise InvalidCapabilityExecutionError("error is required and must not be blank")

        updated = replace(
            execution,
            status=FAILED,
            error=_redactor.redact(error_text),
            completed_at=datetime.now(timezone.utc),
        )
        return self.store.save(updated)

    def get(self, execution_id: str) -> LLMAgentCapabilityExecution:
        """Raises:
        UnknownCapabilityExecutionError: If execution_id was never started
        """
        execution = self.store.get(execution_id)
        if execution is None:
            raise UnknownCapabilityExecutionError(execution_id)
        return execution

    def list_for_agent(self, agent_id: str) -> list:
        self._validate_id(agent_id, "agent_id")
        return self.store.list_for_agent(agent_id)

    def list_for_capability(self, capability_id: str) -> list:
        self._validate_id(capability_id, "capability_id")
        return self.store.list_for_capability(capability_id)

    def _require_running(self, execution_id: str) -> LLMAgentCapabilityExecution:
        execution = self.get(execution_id)
        if execution.status in TERMINAL_STATUSES:
            raise TerminalCapabilityExecutionError(
                f"execution {execution_id!r} is already {execution.status} and cannot be "
                f"transitioned again"
            )
        return execution

    @staticmethod
    def _validate_id(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidCapabilityExecutionError(f"{field_name} is required and must be a non-empty string")
