from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from threading import (
    RLock,
)

from .execution_scheduling_credit import (
    ExecutionSchedulingCredit,
)

from .execution_fair_scheduling_error import (
    ExecutionFairSchedulingError,
)

PRIORITY_WEIGHTS = {
    "LOW": 1.0,
    "NORMAL": 2.0,
    "HIGH": 4.0,
    "CRITICAL": 8.0,
}

DEFAULT_WEIGHT = PRIORITY_WEIGHTS["NORMAL"]

AGING_FACTOR = 0.01

REBALANCE_DECAY = 0.5


class ExecutionFairSchedulingService:
    """
    Selects, from a scope's queued jobs, which one should run next,
    balancing priority against how long a job has waited and how much
    scheduling credit it has already consumed, so no single workload
    can monopolize capacity.

    Composes with an existing job/priority/queue provider (anything
    exposing `queued(scope_id)`, returning an iterable of objects
    with `job_id`, `priority` (one of LOW/NORMAL/HIGH/CRITICAL), and
    `queued_at` (a timezone-aware datetime)), used as the source of
    truth for what is currently queued in a scope.

    Behavior:
    - A job's effective score is its priority weight, boosted the
      longer it has waited, then divided by 1 plus how much credit it
      has already consumed. Priority shifts the odds; it does not
      guarantee the outcome, and unbounded waiting time eventually
      outweighs any priority gap, preventing starvation
    - eligible() ranks a scope's queued jobs highest-score first,
      breaking ties first by queued_at, then by job_id, so the order
      is deterministic for the same underlying state
    - select() is simply the first entry of eligible()
    - consume() raises a job's consumed credit, lowering its future
      score until rebalance() eases it back down

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, job_provider):
        self._job_provider = job_provider
        self._credits_by_job = {}
        self._lock = RLock()

    def eligible(self, scope_id: str) -> tuple:
        """
        Every currently queued job in scope_id, ranked highest
        effective score first.
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            jobs = list(self._job_provider.queued(scope_id))
            now = datetime.now(timezone.utc)

            scored = []

            for job in jobs:
                credit = self._touch_credit(job.job_id, job.priority)
                waited = max((now - job.queued_at).total_seconds(), 0)
                score = (credit.weight * (1 + AGING_FACTOR * waited)) / (1 + credit.consumed)
                scored.append((score, job.queued_at, job.job_id))

            scored.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))

            return tuple(job_id for _, _, job_id in scored)

    def select(self, scope_id: str):
        """
        The single job that should run next in scope_id, or None if
        nothing is queued.
        """

        ordered = self.eligible(scope_id)

        return ordered[0] if ordered else None

    def consume(self, job_id: str, amount: float) -> ExecutionSchedulingCredit:
        """
        Raise a job's consumed credit.

        Raises:
            ExecutionFairSchedulingError: If job_id is None or blank,
                or amount is not a positive number
        """

        self._validate_text(job_id, "job ID")

        if not isinstance(amount, Real) or isinstance(amount, bool) or amount <= 0:
            raise ExecutionFairSchedulingError("Cannot consume a non-positive amount of credit.")

        with self._lock:
            existing = self._credits_by_job.get(job_id)
            weight = existing.weight if existing is not None else DEFAULT_WEIGHT
            consumed = (existing.consumed if existing is not None else 0.0) + amount

            credit = ExecutionSchedulingCredit(
                job_id=job_id,
                weight=weight,
                consumed=consumed,
                updated_at=datetime.now(timezone.utc),
            )

            self._credits_by_job[job_id] = credit

            return credit

    def rebalance(self, scope_id: str) -> tuple:
        """
        Ease off the consumed credit of every currently queued job in
        scope_id that has previously consumed some, restoring their
        scheduling odds over time.

        Returns:
            The credits that were adjusted
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            jobs = list(self._job_provider.queued(scope_id))
            rebalanced = []

            for job in jobs:
                existing = self._credits_by_job.get(job.job_id)

                if existing is None or existing.consumed == 0:
                    continue

                credit = replace(
                    existing,
                    consumed=existing.consumed * REBALANCE_DECAY,
                    updated_at=datetime.now(timezone.utc),
                )

                self._credits_by_job[job.job_id] = credit
                rebalanced.append(credit)

            return tuple(rebalanced)

    def _touch_credit(self, job_id: str, priority: str) -> ExecutionSchedulingCredit:
        weight = PRIORITY_WEIGHTS.get(priority, DEFAULT_WEIGHT)
        existing = self._credits_by_job.get(job_id)
        consumed = existing.consumed if existing is not None else 0.0

        credit = ExecutionSchedulingCredit(
            job_id=job_id,
            weight=weight,
            consumed=consumed,
            updated_at=datetime.now(timezone.utc),
        )

        self._credits_by_job[job_id] = credit

        return credit

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionFairSchedulingError(f"Cannot use an empty or blank {field_name}.")
