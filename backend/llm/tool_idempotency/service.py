import hashlib
import json
from threading import RLock

from ..tool_execution import SUCCEEDED, LLMToolExecution, LLMToolExecutionService
from ..tool_invocation import (
    LLMToolInvocationPlan,
    extract_tool_call_arguments,
    normalize_tool_call,
)


class LLMToolIdempotencyService:
    """Stops the same logical tool call from running twice (Commit #9).

    Keying follows the project's existing convention exactly. The response
    cache (backend.llm.response_cache) already answers "have I seen this
    request before?" by hashing a canonical
    json.dumps(payload, sort_keys=True) with sha256 and prefixing a scope --
    f"{model}:{hash}". This service does the same thing for a tool call:
    f"{tool_name}:{hash}", where the digest covers tool name, subject and
    arguments together. Same algorithm, same canonicalization, same
    in-memory record store every other backend.llm service uses; no
    parallel persistence mechanism is introduced.

    Retry semantics also follow that precedent rather than being redefined.
    LLMResponseCacheService.set refuses to store an unsuccessful response,
    and LLMRetryService retries transient failures against it -- so here a
    failed, denied, or rejected execution is likewise never memoized, and a
    retry of it genuinely re-executes. Only a SUCCEEDED execution is
    remembered.

    Nothing bypasses validation or permissions. A miss runs the call through
    Commit #5's execute(), which re-checks the registry, authorization and
    the argument schema. A hit is re-authorized before the stored result is
    handed back, so a subject whose permission was revoked after a
    successful call does not keep receiving that result.
    """

    def __init__(
        self,
        execution_service: LLMToolExecutionService,
        permission_service=None,
        audit_service=None,
    ):
        """
        Args:
            execution_service: Commit #5's engine. Every genuine execution
                goes through it, gates included
            permission_service: Commit #4's service. When given, a stored
                result is re-authorized before being reused
            audit_service: Commit #8's trail. When given, a freshly executed
                record is appended to it. A reused result is not appended --
                nothing new was executed. The plan's trail must already have
                been started, or record_execution raises as it should
        """
        self._execution_service = execution_service
        self._permission_service = permission_service
        self._audit_service = audit_service
        self._executions_by_key = {}
        self._reuse_counts = {}
        self._lock = RLock()

    # -- keys --------------------------------------------------------------

    @staticmethod
    def _subject_scope(subject) -> str:
        """Idempotency is scoped to the caller, so two subjects never share
        a result even for byte-identical arguments."""
        if subject is None:
            return ""
        if isinstance(subject, str):
            return subject
        if isinstance(subject, (list, tuple, set, frozenset)):
            return ",".join(sorted(str(item) for item in subject))
        return str(subject)

    @staticmethod
    def _call_hash(tool_name: str, subject_scope: str, arguments) -> str:
        """sha256 over the canonical JSON of everything that identifies the call.

        tool name and subject are hashed alongside the arguments, not just
        used as a readable prefix: a subject like "user:ada" contains the
        separator, so a prefix alone could not distinguish (tool "a",
        subject "b:c") from (tool "a:b", subject "c"). Inside the digest
        there is no such ambiguity.
        """
        canonical = json.dumps(
            {"tool_name": tool_name, "subject": subject_scope, "arguments": arguments},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def key(self, tool_call, subject=None) -> str:
        """The idempotency key for one logical tool call.

        Accepts a Commit #3 plan, or the raw tool call it was planned from
        (dict or JSON string) -- read with Commit #3's own reader, so the
        two forms cannot disagree about what the call was. Argument order
        does not matter; argument values do.

        subject is a parameter rather than being read off the call because
        a tool call does not name who is making it, and idempotency is
        scoped to the caller.
        """
        if isinstance(tool_call, LLMToolInvocationPlan):
            tool_name, arguments = tool_call.tool_name, tool_call.arguments
        else:
            normalized = normalize_tool_call(tool_call)
            tool_name = normalized["name"]
            arguments = extract_tool_call_arguments(normalized)

        subject_scope = self._subject_scope(subject)
        # Same shape as LLMResponseCacheService.compute_key: a readable
        # scope prefix, one separator, then a fixed-length digest.
        return f"{tool_name}:{self._call_hash(tool_name, subject_scope, arguments)}"

    # -- reads -------------------------------------------------------------

    def existing(self, key: str):
        """The remembered execution for a key, or None if there is none."""
        with self._lock:
            return self._executions_by_key.get(key)

    def reuse_count(self, key: str) -> int:
        """How many times a stored result has been handed back for this key."""
        with self._lock:
            return self._reuse_counts.get(key, 0)

    def keys(self) -> list:
        with self._lock:
            return list(self._executions_by_key)

    # -- the gate ----------------------------------------------------------

    def execute_once(self, plan, subject) -> LLMToolExecution:
        """Execute a plan, or return the result of the identical call already run.

        The lock spans the check and the execution, so two callers racing
        with the same key produce exactly one execution and both receive
        the same record.
        """
        if not isinstance(plan, LLMToolInvocationPlan):
            raise TypeError(
                f"Cannot execute something that is not an LLMToolInvocationPlan: {plan!r}."
            )

        key = self.key(plan, subject)

        with self._lock:
            remembered = self._executions_by_key.get(key)

            if remembered is not None and self._still_authorized(plan, subject):
                self._reuse_counts[key] = self._reuse_counts.get(key, 0) + 1
                return remembered

            execution = self._execution_service.execute(plan, subject)

            if self._audit_service is not None:
                self._audit_service.record_execution(execution)

            # Only a success is remembered -- the same rule
            # LLMResponseCacheService applies to responses, so a failed call
            # stays retryable.
            if execution.status == SUCCEEDED:
                self._executions_by_key[key] = execution

            return execution

    def _still_authorized(self, plan, subject) -> bool:
        """Whether a stored result may still be handed to this subject.

        Reusing a result must not outlive the permission that produced it,
        so a revoked subject falls through to a normal execute() -- which
        records the denial properly rather than silently returning a stale
        success.
        """
        if self._permission_service is None:
            return True
        return self._permission_service.authorize(plan, subject).allowed

    def forget(self, key: str) -> bool:
        """Drop a remembered result so the next call executes again."""
        with self._lock:
            self._reuse_counts.pop(key, None)
            return self._executions_by_key.pop(key, None) is not None
