from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_job import (
    STATUS_QUEUED,
)

from .execution_schedule_decision import (
    ExecutionScheduleDecision,
)

from .execution_scheduler_error import (
    ExecutionSchedulerError,
)

REASON_SCHEDULED = "scheduled"

REASON_JOB_NOT_ELIGIBLE = "job is not eligible: it is not QUEUED"

REASON_DEPENDENCIES_NOT_READY = "blocked: one or more dependencies are not satisfied"

REASON_OUTSIDE_WINDOW = "blocked: outside the scope's active scheduling window"

REASON_BACKPRESSURE = "blocked: the scope is saturated (backpressure)"

REASON_INSUFFICIENT_RESOURCES = "blocked: insufficient resource capacity"

REASON_ALREADY_RESERVED = "blocked: the job already has an active scheduling reservation"

REASON_NOT_TURN = "blocked: it is not yet this job's turn (priority/fairness)"

REASON_NO_SCHEDULER_AVAILABLE = "blocked: no scheduler is available (failover exhausted)"


class ExecutionSchedulerService:
    """
    Unifies the queue, priority/fairness, dependency, backpressure,
    resource reservation, scheduling reservation, retry, and failover
    components built for workspace execution into a single scheduler
    decision pipeline for a job.

    Every collaborator is reused as-is (duck-typed to the interface
    each earlier service already exposes):
        queue_service: status(job_id) -> str; cancel(job_id)
            (ExecutionJobQueueService)
        dependency_service: ready(job_id) -> bool
            (ExecutionJobDependencyService)
        window_service: active(scope_id, timestamp) -> bool
            (ExecutionSchedulingWindowService)
        backpressure_service: can_enqueue(scope_id) -> bool
            (ExecutionBackpressureService)
        resource_reservation_service: available(resource_type) -> float
            (ExecutionResourceReservationService)
        fair_scheduling_service: select(scope_id) -> job_id or None
            (ExecutionFairSchedulingService)
        failover_service: execute(scope_id); select(scope_id) -> scheduler_id or None
            (ExecutionSchedulerFailoverService)
        scheduling_reservation_service: active(job_id); acquire(job_id, scheduler_id); release(reservation_id)
            (ExecutionSchedulingReservationService)
        retry_service: retry(job_id, scope_id) (ExecutionSchedulingRetryService)
        resource_requirements: an optional {job_id: (resource_type, amount)}
            mapping used for the resource capacity check; jobs absent
            from it skip that check

    Behavior:
    - evaluate() runs every gate (dependencies, window, backpressure,
      resources, an existing scheduling reservation, then priority/
      fairness, then failover) without any side effect, and reports
      what schedule() would decide
    - schedule() runs the same pipeline; if every gate passes, it
      acquires a scheduling reservation for the assigned scheduler
      and allows the job. If any gate fails, it best-effort applies
      the scope's retry policy (a scope with no retry policy
      configured simply skips this) and denies the job. Either way,
      exactly one ExecutionScheduleDecision is recorded as job_id's
      latest decision
    - cancel() releases any active scheduling reservation for job_id
      and cancels it in the job queue

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        queue_service,
        dependency_service,
        window_service,
        backpressure_service,
        resource_reservation_service,
        fair_scheduling_service,
        failover_service,
        scheduling_reservation_service,
        retry_service,
        resource_requirements: dict = None,
    ):
        self._queue_service = queue_service
        self._dependency_service = dependency_service
        self._window_service = window_service
        self._backpressure_service = backpressure_service
        self._resource_reservation_service = resource_reservation_service
        self._fair_scheduling_service = fair_scheduling_service
        self._failover_service = failover_service
        self._scheduling_reservation_service = scheduling_reservation_service
        self._retry_service = retry_service
        self._resource_requirements = dict(resource_requirements or {})
        self._decisions_by_job = {}
        self._lock = RLock()

    def schedule(self, job_id: str, scope_id: str) -> ExecutionScheduleDecision:
        """
        Run job_id through the full scheduler decision pipeline,
        recording and returning the outcome.

        Raises:
            ExecutionSchedulerError: If job_id or scope_id is None or
                blank, or job_id is unknown to the job queue
        """

        self._validate_text(job_id, "job ID")
        self._validate_text(scope_id, "scope ID")

        with self._lock:
            allowed, reason, scheduler_id = self._run_pipeline(job_id, scope_id)

            if allowed:
                try:
                    self._scheduling_reservation_service.acquire(job_id, scheduler_id)
                except Exception as error:
                    allowed = False
                    scheduler_id = None
                    reason = f"blocked: failed to acquire a scheduling reservation ({error})"

            if not allowed:
                self._apply_retry(job_id, scope_id)

            decision = ExecutionScheduleDecision(
                decision_id=str(uuid4()),
                job_id=job_id,
                scheduler_id=scheduler_id,
                allowed=allowed,
                reason=reason,
                created_at=datetime.now(timezone.utc),
            )

            self._decisions_by_job[job_id] = decision

            return decision

    def evaluate(self, job_id: str, scope_id: str) -> ExecutionScheduleDecision:
        """
        Report what schedule() would decide for job_id right now,
        without acquiring a reservation, applying retry, or recording
        the outcome as job_id's decision.

        Raises:
            ExecutionSchedulerError: If job_id or scope_id is None or
                blank, or job_id is unknown to the job queue
        """

        self._validate_text(job_id, "job ID")
        self._validate_text(scope_id, "scope ID")

        with self._lock:
            allowed, reason, scheduler_id = self._run_pipeline(job_id, scope_id)

            return ExecutionScheduleDecision(
                decision_id=str(uuid4()),
                job_id=job_id,
                scheduler_id=scheduler_id,
                allowed=allowed,
                reason=reason,
                created_at=datetime.now(timezone.utc),
            )

    def decision(self, job_id: str) -> ExecutionScheduleDecision:
        """
        The most recent decision schedule() recorded for job_id.

        Raises:
            ExecutionSchedulerError: If job_id is None or blank, or
                no decision has been recorded for it
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            recorded = self._decisions_by_job.get(job_id)

            if recorded is None:
                raise ExecutionSchedulerError(f"No schedule decision is recorded for job ID {job_id!r}.")

            return recorded

    def cancel(self, job_id: str) -> None:
        """
        Release any active scheduling reservation for job_id and
        cancel it in the job queue.

        Raises:
            ExecutionSchedulerError: If job_id is None or blank, or
                the job queue rejects the cancellation
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            reservation = self._scheduling_reservation_service.active(job_id)

            if reservation is not None:
                self._scheduling_reservation_service.release(reservation.reservation_id)

            try:
                self._queue_service.cancel(job_id)
            except Exception as error:
                raise ExecutionSchedulerError(f"Cannot cancel job ID {job_id!r}.") from error

            self._decisions_by_job.pop(job_id, None)

    def _run_pipeline(self, job_id: str, scope_id: str):
        try:
            status = self._queue_service.status(job_id)
        except Exception as error:
            raise ExecutionSchedulerError(f"Cannot schedule job ID {job_id!r}: it is unknown.") from error

        if status != STATUS_QUEUED:
            return False, REASON_JOB_NOT_ELIGIBLE, None

        if not self._dependency_service.ready(job_id):
            return False, REASON_DEPENDENCIES_NOT_READY, None

        if not self._window_service.active(scope_id, datetime.now(timezone.utc)):
            return False, REASON_OUTSIDE_WINDOW, None

        if not self._backpressure_service.can_enqueue(scope_id):
            return False, REASON_BACKPRESSURE, None

        requirement = self._resource_requirements.get(job_id)

        if requirement is not None:
            resource_type, amount = requirement

            if self._resource_reservation_service.available(resource_type) < amount:
                return False, REASON_INSUFFICIENT_RESOURCES, None

        if self._scheduling_reservation_service.active(job_id) is not None:
            return False, REASON_ALREADY_RESERVED, None

        turn = self._fair_scheduling_service.select(scope_id)

        if turn is not None and turn != job_id:
            return False, REASON_NOT_TURN, None

        self._failover_service.execute(scope_id)
        scheduler_id = self._failover_service.select(scope_id)

        if scheduler_id is None:
            return False, REASON_NO_SCHEDULER_AVAILABLE, None

        return True, REASON_SCHEDULED, scheduler_id

    def _apply_retry(self, job_id: str, scope_id: str) -> None:
        try:
            self._retry_service.retry(job_id, scope_id)
        except Exception:
            pass

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulerError(f"Cannot use an empty or blank {field_name}.")
