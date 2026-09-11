from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock
from typing import Optional

from backend.agent_task_readiness import LLMAgentTaskReadinessService

from .in_memory_store import InMemoryAgentTaskQueueStore
from .models import InvalidQueueEntryError, QueueEntry
from .store import AgentTaskQueueStore


class UnknownQueueEntryError(KeyError):
    """Raised when claim()/remove() is given a task_id that is not
    currently queued."""


class TaskNotReadyError(ValueError):
    """Raised when enqueue() is given a task_id that does not currently
    satisfy backend.agent_task_readiness.LLMAgentTaskReadinessService's
    own readiness semantics (Rule: "Only tasks that satisfy existing
    readiness semantics may be enqueued")."""


class ConflictingClaimError(ValueError):
    """Raised when claim() is attempted by an actor other than the one
    who already claimed the entry (Rule: "Claiming must prevent
    duplicate simultaneous claims")."""


class LLMAgentTaskQueueService:
    """A persistent queue of task_ids that are ready for work --
    enqueue, inspect, claim, remove. Never a worker, scheduler, or
    executor (Rule: "No task execution, scheduling, retry, or worker
    implementation"): nothing here ever runs a task, only records that
    it is waiting to be picked up and by whom.

    Queue membership is deliberately disjoint from
    backend.agent_task_lifecycle's own AgentTask.current_state (Rule:
    "Queue state is not task lifecycle state") -- enqueue()/remove()
    never call transition(), and a task leaving the queue (via remove())
    says nothing about what its lifecycle state becomes next; that
    remains entirely this caller's own business, exactly as
    execution/scheduling itself is out of scope here.

    Readiness is gated through the existing
    backend.agent_task_readiness.LLMAgentTaskReadinessService.is_ready()
    rather than a second notion of "ready" invented here (Rule: "reuse
    existing ... readiness ... patterns"): enqueue() only ever asks that
    service, never inspects lifecycle state, dependencies, or policy
    itself.

    enqueue() is idempotent (Rule: "Repeated enqueue follows existing
    idempotency conventions"): a second enqueue() of an already-queued
    task_id returns the existing entry unchanged (same queued_at,
    priority, and claim state), the same "idempotency is checked before
    any other guard" precedent backend.agent_policy_risk_review_queue.
    LLMAgentRiskReviewQueue.enqueue() already establishes -- it never
    re-validates readiness, or updates priority, for an already-queued
    task_id.

    claim() establishes exclusive ownership using this repository's own
    concurrency primitive (threading.RLock, the same one backend.
    agent_execution_budget.LLMAgentExecutionBudgetService and backend.
    agent_checkpointing already guard their own mutating methods with)
    rather than inventing a new locking scheme: enqueue()/claim()/
    remove() all run under one instance-wide lock, so two claim() calls
    for the same task_id can never both observe it unclaimed. An entry
    already claimed by the same claimant_id is a no-op re-claim
    (returns the existing entry); claimed by anyone else raises
    ConflictingClaimError -- the same "same actor is a no-op, a
    different one conflicts" discipline
    LLMAgentRiskReviewQueue.claim() already uses.

    peek() orders entries deterministically: priority first (higher
    first, the same convention backend.llm.context.LLMContextService's
    own ranking already uses for its LLMContextItem.priority), then
    queued_at (earlier first -- FIFO among equal priority), then task_id
    as a final, total tie-break -- the same
    (-priority, timestamp, id)-shaped sort key backend.
    agent_memory_retrieval.LLMAgentMemoryRetrievalService and backend.
    agent_strategy_retrieval.LLMAgentStrategyRetrievalService already
    use for their own ranked results.

    Only an InMemory store is provided by default; a
    JsonAgentTaskQueueStore is available for durable, file-backed queues
    since every field on QueueEntry is plain, JSON-round-trippable data
    (unlike, e.g., backend.agent_policy_risk_review_queue's own
    ReviewItem, which embeds a full RiskDecision and is therefore
    InMemory-only).
    """

    def __init__(self, readiness_service: LLMAgentTaskReadinessService, store: AgentTaskQueueStore = None):
        """
        Args:
            readiness_service: The exact
                backend.agent_task_readiness.LLMAgentTaskReadinessService
                instance wired to the same lifecycle/dependency/policy
                state this queue's own task_ids live in -- required,
                never defaulted, the same "no usable zero-argument
                default" discipline
                backend.agent_task_readiness_projection.
                LLMAgentTaskReadinessProjectionService already applies
                to its own lifecycle_service argument.
            store: Defaults to a fresh InMemoryAgentTaskQueueStore.
        """
        self._readiness_service = readiness_service
        self.store = store if store is not None else InMemoryAgentTaskQueueStore()
        self._lock = RLock()

    def enqueue(self, task_id: str, priority: Optional[int] = None) -> QueueEntry:
        """Enqueue task_id for ready work, or return its existing entry
        if it is already queued (idempotent -- see this class's own
        docstring).

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank, or
                priority is given and is not an int
            TaskNotReadyError: If task_id is not currently queued, and
                does not satisfy readiness_service.is_ready()
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")
        if priority is not None and not isinstance(priority, int):
            raise InvalidQueueEntryError("priority must be an int when given")

        with self._lock:
            existing = self.store.get(task_id)
            if existing is not None:
                return existing

            if not self._readiness_service.is_ready(task_id):
                raise TaskNotReadyError(
                    f"cannot enqueue task {task_id!r}: it does not satisfy current readiness checks"
                )

            entry = QueueEntry(task_id=task_id, priority=priority if priority is not None else 0)
            return self.store.save(entry)

    def peek(self, limit: Optional[int] = None) -> list:
        """Every currently queued entry, in deterministic priority order
        (see this class's own docstring), optionally capped to the
        first limit entries. Never claims or removes anything.

        Raises:
            InvalidQueueEntryError: If limit is given and is not a
                non-negative int
        """
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidQueueEntryError("limit must be a non-negative int when given")

        entries = sorted(self.store.list(), key=lambda entry: (-entry.priority, entry.queued_at, entry.task_id))
        return entries if limit is None else entries[:limit]

    def claim(self, task_id: str, claimant_id: str) -> QueueEntry:
        """Claim exclusive ownership of a queued task_id for
        claimant_id. Re-claiming by the same claimant_id is a no-op.

        Raises:
            InvalidQueueEntryError: If claimant_id is missing or blank
            UnknownQueueEntryError: If task_id is not currently queued
            ConflictingClaimError: If task_id is already claimed by a
                different claimant_id
        """
        if not claimant_id or not isinstance(claimant_id, str):
            raise InvalidQueueEntryError("claimant_id is required and must be a non-empty string")

        with self._lock:
            entry = self.store.get(task_id)
            if entry is None:
                raise UnknownQueueEntryError(task_id)

            if entry.claimant_id is not None:
                if entry.claimant_id == claimant_id:
                    return entry
                raise ConflictingClaimError(
                    f"cannot claim task {task_id!r}: already claimed by {entry.claimant_id!r}"
                )

            claimed = replace(entry, claimant_id=claimant_id, claimed_at=datetime.now(timezone.utc))
            return self.store.save(claimed)

    def remove(self, task_id: str) -> None:
        """Remove task_id's entry from the queue entirely -- claimed or
        not. Never touches task_id's own lifecycle state (Rule: "Queue
        state is not task lifecycle state").

        Raises:
            UnknownQueueEntryError: If task_id is not currently queued
        """
        with self._lock:
            if not self.store.delete(task_id):
                raise UnknownQueueEntryError(task_id)

    def contains(self, task_id: str) -> bool:
        """Whether task_id currently has a queue entry, claimed or
        not."""
        return self.store.get(task_id) is not None
